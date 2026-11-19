import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { X } from 'lucide-react';
import LoginView from './components/LoginView';
import Sidebar from './components/Sidebar';
import Topbar from './components/Topbar';
import ChangePasswordModal from './components/ChangePasswordModal';
import OverviewPage from './pages/OverviewPage';
import SitesPage from './pages/SitesPage';
import DocumentsPage from './pages/DocumentsPage';
import QueriesAuditPage from './pages/QueriesAuditPage';
import ReportsExportPage from './pages/ReportsExportPage';
import OrganizationsPage from './pages/OrganizationsPage';
import {
  getStoredSession,
  clearStoredSession,
  updateStoredUser,
  setUnauthorizedHandler,
  fetchAdminMe,
  fetchOrganizations,
  fetchSites,
  checkServicesHealth,
  extractArray,
} from './services/api';
import { resolveSiteLabels } from './utils/labels';

export default function App() {
  const [session, setSession] = useState(() => getStoredSession());
  const [loginNotice, setLoginNotice] = useState('');
  const [activePage, setActivePage] = useState('overview');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [changePwdOpen, setChangePwdOpen] = useState(false);

  const [filters, setFilters] = useState({
    orgId: '',
    siteId: '',
    timeRange: '30d',
  });

  const [organizations, setOrganizations] = useState([]);
  const [sites, setSites] = useState([]);
  const [health, setHealth] = useState(undefined);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [toasts, setToasts] = useState([]);

  const addToast = useCallback((message, type = 'info') => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    setToasts((prev) => [...prev.slice(-3), { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4500);
  }, []);

  const handleLogout = useCallback((notice = '') => {
    clearStoredSession();
    setSession(null);
    setOrganizations([]);
    setSites([]);
    setActivePage('overview');
    setFilters({ orgId: '', siteId: '', timeRange: '30d' });
    setLoginNotice(typeof notice === 'string' ? notice : '');
  }, []);

  useEffect(() => {
    setUnauthorizedHandler((msg) => {
      handleLogout(msg || 'Sesión expirada. Vuelve a iniciar sesión.');
    });
    return () => setUnauthorizedHandler(null);
  }, [handleLogout]);

  const loadCatalogAndHealth = useCallback(async () => {
    if (!session?.token) return;
    const isGlobal = session.user?.role === 'GLOBAL_ADMIN';
    const [healthRes, orgsRes, sitesRes] = await Promise.allSettled([
      checkServicesHealth(),
      fetchOrganizations(),
      fetchSites(isGlobal && filters.orgId ? filters.orgId : undefined),
    ]);

    if (healthRes.status === 'fulfilled') setHealth(healthRes.value);
    if (orgsRes.status === 'fulfilled') setOrganizations(extractArray(orgsRes.value));
    if (sitesRes.status === 'fulfilled') setSites(extractArray(sitesRes.value));
  }, [session?.token, session?.user?.role, filters.orgId]);

  // Verify token & refresh profile when session starts
  useEffect(() => {
    if (!session?.token) return undefined;
    let cancelled = false;
    fetchAdminMe()
      .then((profile) => {
        if (cancelled || !profile) return;
        updateStoredUser(profile);
        setSession((prev) => (prev ? { ...prev, user: profile } : prev));
      })
      .catch(() => {
        // 401 handled globally by setUnauthorizedHandler
      });
    return () => {
      cancelled = true;
    };
  }, [session?.token]);

  useEffect(() => {
    if (!session?.token) return;
    loadCatalogAndHealth();
  }, [session?.token, loadCatalogAndHealth]);

  const user = session?.user;
  const activeOrg = useMemo(() => {
    if (!user) return null;
    if (user.role === 'GLOBAL_ADMIN') {
      return organizations.find((o) => o.org_id === filters.orgId) || null;
    }
    return organizations.find((o) => o.org_id === user.org_id) || null;
  }, [user, organizations, filters.orgId]);

  const siteLabels = useMemo(
    () => resolveSiteLabels(activeOrg || user),
    [activeOrg, user]
  );

  async function handleRefreshAll() {
    setRefreshing(true);
    try {
      await loadCatalogAndHealth();
      setRefreshKey((k) => k + 1);
    } finally {
      setRefreshing(false);
    }
  }

  function handleLoginSuccess(newSession) {
    setLoginNotice('');
    setSession(newSession);
    setActivePage('overview');
    setFilters({
      orgId:
        newSession.user?.role === 'GLOBAL_ADMIN' ? '' : newSession.user?.org_id || '',
      siteId: '',
      timeRange: '30d',
    });
  }

  function handleOpenSiteDocuments(site) {
    setFilters((prev) => ({
      ...prev,
      orgId: session?.user?.role === 'GLOBAL_ADMIN' ? site.org_id || prev.orgId : prev.orgId,
      siteId: site.site_id,
    }));
    setActivePage('documents');
  }

  function handleOpenSiteMetrics(site) {
    setFilters((prev) => ({
      ...prev,
      orgId: session?.user?.role === 'GLOBAL_ADMIN' ? site.org_id || prev.orgId : prev.orgId,
      siteId: site.site_id,
    }));
    setActivePage('overview');
  }

  function handleInspectOrgSites(orgId) {
    setFilters((prev) => ({
      ...prev,
      orgId,
      siteId: '',
    }));
    setActivePage('sites');
  }

  if (!session?.token) {
    return (
      <LoginView
        initialNotice={loginNotice}
        onLoginSuccess={handleLoginSuccess}
      />
    );
  }

  const safePage =
    activePage === 'organizations' && user?.role !== 'GLOBAL_ADMIN'
      ? 'overview'
      : activePage;

  return (
    <div className="app-shell">
      <Sidebar
        activePage={safePage}
        onNavigate={setActivePage}
        user={user}
        siteLabels={siteLabels}
        mobileOpen={mobileMenuOpen}
        onCloseMobile={() => setMobileMenuOpen(false)}
      />

      <div className="main-col">
        <Topbar
          user={user}
          organizations={organizations}
          sites={sites}
          siteLabels={siteLabels}
          filters={filters}
          onChangeFilters={setFilters}
          onRefresh={handleRefreshAll}
          refreshing={refreshing}
          health={health}
          onOpenChangePassword={() => setChangePwdOpen(true)}
          onLogout={() => handleLogout('')}
          onOpenMobileMenu={() => setMobileMenuOpen(true)}
        />

        <main className="page-content">
          {safePage === 'overview' ? (
            <OverviewPage
              filters={filters}
              sites={sites}
              siteLabels={siteLabels}
              refreshKey={refreshKey}
              onToast={addToast}
            />
          ) : null}

          {safePage === 'sites' ? (
            <SitesPage
              user={user}
              organizations={organizations}
              activeOrg={activeOrg}
              siteLabels={siteLabels}
              filters={filters}
              refreshKey={refreshKey}
              onReloadCatalog={loadCatalogAndHealth}
              onOpenSiteDocuments={handleOpenSiteDocuments}
              onOpenSiteMetrics={handleOpenSiteMetrics}
              onToast={addToast}
            />
          ) : null}

          {safePage === 'documents' ? (
            <DocumentsPage
              user={user}
              sites={sites}
              siteLabels={siteLabels}
              filters={filters}
              refreshKey={refreshKey}
              onToast={addToast}
            />
          ) : null}

          {safePage === 'audit' ? (
            <QueriesAuditPage
              filters={filters}
              sites={sites}
              siteLabels={siteLabels}
              refreshKey={refreshKey}
              onToast={addToast}
            />
          ) : null}

          {safePage === 'reports' ? (
            <ReportsExportPage
              filters={filters}
              sites={sites}
              siteLabels={siteLabels}
              refreshKey={refreshKey}
              onToast={addToast}
            />
          ) : null}

          {safePage === 'organizations' && user?.role === 'GLOBAL_ADMIN' ? (
            <OrganizationsPage
              currentUser={user}
              filters={filters}
              refreshKey={refreshKey}
              onReloadCatalog={loadCatalogAndHealth}
              onInspectOrgSites={handleInspectOrgSites}
              onToast={addToast}
            />
          ) : null}
        </main>
      </div>

      <ChangePasswordModal
        open={changePwdOpen}
        onClose={() => setChangePwdOpen(false)}
        onSuccess={(msg) => addToast(msg, 'success')}
      />

      {toasts.length > 0 ? (
        <div className="toast-stack" role="status" aria-live="polite">
          {toasts.map((t) => (
            <div key={t.id} className={`toast toast--${t.type || 'info'}`}>
              <span>{t.message}</span>
              <button
                type="button"
                className="btn btn-sm btn-icon"
                style={{ width: 22, height: 22, border: 'none' }}
                onClick={() => setToasts((prev) => prev.filter((item) => item.id !== t.id))}
                aria-label="Cerrar aviso"
              >
                <X size={13} />
              </button>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

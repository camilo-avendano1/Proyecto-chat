import React, { useEffect, useState, useMemo, useCallback, useRef } from 'react';
import {
  FileText,
  UploadCloud,
  Search,
  Eye,
  RefreshCw,
  Trash2,
  CheckCircle2,
  AlertTriangle,
  Copy,
  FileCode2,
  X,
} from 'lucide-react';
import Modal from '../components/Modal';
import {
  fetchDocuments,
  uploadDocument,
  fetchDocumentChunks,
  syncDocumentVector,
  deleteDocument,
  extractArray,
} from '../services/api';
import { formatBytes, formatDateTime, formatNumber } from '../utils/export';
import { formatScopeLabel } from '../utils/labels';

const MAX_FILE_BYTES = 15 * 1024 * 1024; // 15 MB
const ALLOWED_EXTENSIONS = ['.pdf', '.xlsx', '.csv', '.docx', '.txt', '.md', '.json'];

function hasAllowedExtension(filename) {
  const lower = String(filename || '').toLowerCase();
  return ALLOWED_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

function getDocHash(doc) {
  return doc?.content_hash || doc?.sha256 || doc?.file_hash || '';
}

function getDocSyncStatus(doc) {
  return (
    doc?.vector_sync_status ||
    doc?.sync_status ||
    doc?.vector_status ||
    'LOCAL_INDEXED'
  ).toUpperCase();
}

function getDocSyncDetail(doc) {
  return doc?.vector_sync_detail || doc?.sync_error || doc?.last_error || '';
}

function getDocFileSize(doc) {
  return doc?.file_size_bytes ?? doc?.file_size ?? doc?.size_bytes ?? doc?.content_bytes ?? 0;
}

function readFileAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result || '');
      const commaIdx = result.indexOf(',');
      resolve(commaIdx >= 0 ? result.slice(commaIdx + 1) : result);
    };
    reader.onerror = () => reject(new Error('No se pudo leer el archivo seleccionado.'));
    reader.readAsDataURL(file);
  });
}

function ScopeBadge({ scope, siteLabel }) {
  const s = (scope || 'SITE').toUpperCase();
  const cls =
    s === 'GLOBAL'
      ? 'badge--violet'
      : s === 'ORGANIZATION'
      ? 'badge--amber'
      : 'badge--blue';
  return <span className={`badge ${cls}`}>{formatScopeLabel(s, siteLabel)}</span>;
}

function SyncStatusBadge({ status, errorDetail }) {
  const s = (status || 'LOCAL_INDEXED').toUpperCase();
  if (s === 'SYNCED_REMOTE') {
    return (
      <span className="badge badge--emerald" title="Sincronizado con el motor de búsqueda del asistente">
        Sincronizado
      </span>
    );
  }
  if (s === 'SYNC_ERROR') {
    return (
      <span
        className="badge badge--rose"
        title={errorDetail || 'Error al sincronizar el documento con el asistente'}
      >
        Error de sincronización
      </span>
    );
  }
  return (
    <span className="badge badge--amber" title="Procesado localmente en fragmentos">
      Guardado localmente
    </span>
  );
}

export default function DocumentsPage({
  user,
  sites = [],
  siteLabels = { singular: 'Sede', plural: 'Sedes' },
  filters,
  refreshKey,
  onToast,
}) {
  const isGlobalAdmin = user?.role === 'GLOBAL_ADMIN';
  const fileInputRef = useRef(null);

  const scopedSites = useMemo(() => {
    if (isGlobalAdmin && filters.orgId) {
      return sites.filter((s) => s.org_id === filters.orgId);
    }
    return sites;
  }, [sites, isGlobalAdmin, filters.orgId]);

  const siteMap = useMemo(() => {
    const m = {};
    sites.forEach((s) => {
      if (s.site_id) m[s.site_id] = s;
    });
    return m;
  }, [sites]);

  // Upload form state
  const [uploadMode, setUploadMode] = useState('file'); // 'file' | 'text'
  const [scope, setScope] = useState('SITE');
  const [targetSiteId, setTargetSiteId] = useState(filters.siteId || '');
  const [title, setTitle] = useState('');
  const [tagsInput, setTagsInput] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [directFilename, setDirectFilename] = useState('guia-directa.md');
  const [directText, setDirectText] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadFeedback, setUploadFeedback] = useState(null);

  // Documents table state
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [docsError, setDocsError] = useState('');
  const [documents, setDocuments] = useState([]);
  const [totalDocs, setTotalDocs] = useState(0);
  const [searchTerm, setSearchTerm] = useState('');
  const [appliedSearch, setAppliedSearch] = useState('');
  const [scopeFilter, setScopeFilter] = useState('ALL');
  const [offset, setOffset] = useState(0);
  const limit = 25;

  // Row operations
  const [syncingDocId, setSyncingDocId] = useState('');
  const [docToDelete, setDocToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);

  // Fragments preview modal
  const [chunksModalOpen, setChunksModalOpen] = useState(false);
  const [chunksLoading, setChunksLoading] = useState(false);
  const [chunksData, setChunksData] = useState(null);
  const [chunkSearch, setChunkSearch] = useState('');

  useEffect(() => {
    if (filters.siteId) {
      setTargetSiteId(filters.siteId);
    } else if (scopedSites.length > 0 && !scopedSites.some((s) => s.site_id === targetSiteId)) {
      setTargetSiteId(scopedSites[0].site_id);
    }
  }, [filters.siteId, scopedSites, targetSiteId]);

  const loadDocuments = useCallback(async () => {
    setLoadingDocs(true);
    setDocsError('');
    try {
      const params = {
        limit,
        offset,
      };
      if (filters.orgId) params.org_id = filters.orgId;
      if (filters.siteId) params.site_id = filters.siteId;
      if (scopeFilter && scopeFilter !== 'ALL') params.scope = scopeFilter;
      if (appliedSearch.trim()) params.search = appliedSearch.trim();

      const res = await fetchDocuments(params);
      setDocuments(extractArray(res));
      setTotalDocs(Number(res?.total ?? 0));
    } catch (err) {
      setDocsError(err.message || 'No se pudieron cargar los documentos.');
    } finally {
      setLoadingDocs(false);
    }
  }, [filters.orgId, filters.siteId, scopeFilter, appliedSearch, offset]);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments, refreshKey]);

  function handleFilePicked(file) {
    if (!file) return;
    if (!hasAllowedExtension(file.name)) {
      setUploadFeedback({
        type: 'error',
        title: 'Formato no soportado',
        message: `Formatos permitidos: ${ALLOWED_EXTENSIONS.join(', ')}`,
      });
      return;
    }
    if (file.size > MAX_FILE_BYTES) {
      setUploadFeedback({
        type: 'error',
        title: 'Archivo excede el límite de 15 MB',
        message: `El archivo "${file.name}" pesa ${formatBytes(file.size)}.`,
      });
      return;
    }
    setUploadFeedback(null);
    setSelectedFile(file);
    if (!title.trim()) {
      const withoutExt = file.name.replace(/\.[^.]+$/, '');
      setTitle(withoutExt);
    }
  }

  async function handleUploadSubmit(e) {
    e.preventDefault();
    setUploadFeedback(null);

    const lowerSingular = siteLabels.singular.toLowerCase();

    if (scope === 'SITE' && !targetSiteId) {
      setUploadFeedback({
        type: 'error',
        title: `${siteLabels.singular} requerida`,
        message: `Selecciona una ${lowerSingular} destino para el alcance "${formatScopeLabel('SITE', siteLabels.singular)}".`,
      });
      return;
    }

    if (uploadMode === 'file' && !selectedFile) {
      setUploadFeedback({
        type: 'error',
        title: 'Selecciona un archivo',
        message: 'Arrastra un documento al área de carga o selecciónalo desde tu equipo.',
      });
      return;
    }

    if (uploadMode === 'text' && !directText.trim()) {
      setUploadFeedback({
        type: 'error',
        title: 'Contenido vacío',
        message: 'Pega el texto o guía que deseas agregar al asistente.',
      });
      return;
    }

    const tags = tagsInput
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean);

    const chosenSite = siteMap[targetSiteId];
    const resolvedOrgId =
      scope === 'GLOBAL'
        ? undefined
        : scope === 'SITE'
        ? chosenSite?.org_id || filters.orgId || user?.org_id || undefined
        : filters.orgId || user?.org_id || undefined;

    setUploading(true);
    try {
      const payload = {
        title:
          title.trim() ||
          (uploadMode === 'file' ? selectedFile.name : directFilename.trim() || 'Documento Directo'),
        filename:
          uploadMode === 'file'
            ? selectedFile.name
            : directFilename.trim() || 'guia-directa.md',
        scope,
        tags,
      };
      if (resolvedOrgId) payload.org_id = resolvedOrgId;
      if (scope === 'SITE' && targetSiteId) payload.site_id = targetSiteId;

      if (uploadMode === 'file') {
        payload.content_base64 = await readFileAsBase64(selectedFile);
      } else {
        payload.content_text = directText;
      }

      const res = await uploadDocument(payload);
      const doc = res?.document || {};
      const syncStatus = getDocSyncStatus(doc);

      if (res?.deduplicated) {
        setUploadFeedback({
          type: 'warning',
          title: 'Documento duplicado detectado (SHA-256)',
          message:
            res.message ||
            `El archivo con huella ${String(getDocHash(doc)).slice(0, 12)} ya existía en este alcance; no se duplicaron fragmentos.`,
          document: doc,
        });
        if (onToast) onToast('Documento ya cargado (deduplicado SHA-256).', 'warning');
      } else if (syncStatus === 'SYNC_ERROR') {
        setUploadFeedback({
          type: 'warning',
          title: 'Guardado localmente con error de sincronización',
          message:
            getDocSyncDetail(doc) ||
            res?.message ||
            'El documento fue dividido en fragmentos localmente, pero falló la sincronización con el asistente.',
          document: doc,
        });
        if (onToast) onToast('Documento guardado localmente; falló sincronización.', 'warning');
      } else {
        setUploadFeedback({
          type: 'success',
          title:
            syncStatus === 'SYNCED_REMOTE'
              ? 'Documento procesado y sincronizado con el asistente'
              : 'Documento procesado localmente',
          message:
            res?.message ||
            `Procesado en ${formatNumber(doc.chunk_count ?? 0)} fragmentos.`,
          document: doc,
        });
        if (onToast) onToast('Documento agregado al asistente exitosamente.', 'success');
      }

      setSelectedFile(null);
      setDirectText('');
      setTitle('');
      setTagsInput('');
      if (fileInputRef.current) fileInputRef.current.value = '';
      setOffset(0);
      await loadDocuments();
    } catch (err) {
      setUploadFeedback({
        type: 'error',
        title: 'Error al procesar el documento',
        message: err.message || 'No se pudo cargar o procesar el documento.',
      });
    } finally {
      setUploading(false);
    }
  }

  async function handleOpenChunks(doc) {
    const docId = doc.doc_id || doc.id;
    setChunksModalOpen(true);
    setChunksLoading(true);
    setChunksData(null);
    setChunkSearch('');
    try {
      const res = await fetchDocumentChunks(docId);
      setChunksData(res);
    } catch (err) {
      if (onToast) onToast(err.message || 'No se pudieron cargar los fragmentos.', 'error');
      setChunksModalOpen(false);
    } finally {
      setChunksLoading(false);
    }
  }

  async function handleSyncDoc(doc) {
    const docId = doc.doc_id || doc.id;
    setSyncingDocId(docId);
    try {
      const res = await syncDocumentVector(docId);
      const updated = res?.document || res || {};
      const status = getDocSyncStatus(updated);
      if (status === 'SYNC_ERROR') {
        if (onToast) {
          onToast(
            getDocSyncDetail(updated) || 'La sincronización reportó un error.',
            'warning'
          );
        }
      } else {
        if (onToast) onToast('Documento sincronizado con el asistente.', 'success');
      }
      await loadDocuments();
    } catch (err) {
      if (onToast) onToast(err.message || 'Error al sincronizar documento.', 'error');
    } finally {
      setSyncingDocId('');
    }
  }

  async function handleConfirmDelete() {
    if (!docToDelete) return;
    const docId = docToDelete.doc_id || docToDelete.id;
    setDeleting(true);
    try {
      await deleteDocument(docId);
      if (onToast) onToast(`Documento "${docToDelete.title}" eliminado.`, 'success');
      setDocToDelete(null);
      await loadDocuments();
    } catch (err) {
      if (onToast) onToast(err.message || 'No se pudo eliminar el documento.', 'error');
    } finally {
      setDeleting(false);
    }
  }

  const filteredChunks = useMemo(() => {
    const chunks = chunksData?.chunks || [];
    const q = chunkSearch.trim().toLowerCase();
    if (!q) return chunks;
    return chunks.filter(
      (c) =>
        String(c.text || c.content || '').toLowerCase().includes(q) ||
        String(c.section || c.heading || '').toLowerCase().includes(q)
    );
  }, [chunksData, chunkSearch]);

  const lowerSingular = siteLabels.singular.toLowerCase();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div className="page-header">
        <div>
          <h1 className="page-title">Documentos del Asistente</h1>
          <p className="page-subtitle">
            Sube archivos o redacta guías para que el asistente responda con información actualizada y verificada.
          </p>
        </div>
      </div>

      {/* Upload & Indexing Card */}
      <section className="card">
        <div className="card-header">
          <div>
            <h2 className="card-title">
              <UploadCloud size={17} />
              <span>Agregar Documento al Asistente</span>
            </h2>
            <p className="card-subtitle">
              Soporta PDF, XLSX, CSV, DOCX, TXT, MD y JSON (máximo 15 MB) o contenido escrito directamente.
            </p>
          </div>
          <div className="segmented">
            <button
              type="button"
              className={`segmented-btn ${uploadMode === 'file' ? 'segmented-btn--active' : ''}`}
              onClick={() => setUploadMode('file')}
            >
              Subir Archivo
            </button>
            <button
              type="button"
              className={`segmented-btn ${uploadMode === 'text' ? 'segmented-btn--active' : ''}`}
              onClick={() => setUploadMode('text')}
            >
              Escribir Texto Directo
            </button>
          </div>
        </div>

        <form onSubmit={handleUploadSubmit} className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {uploadFeedback ? (
            <div
              className={`alert ${
                uploadFeedback.type === 'success'
                  ? 'alert--success'
                  : uploadFeedback.type === 'warning'
                  ? 'alert--warning'
                  : 'alert--error'
              }`}
              role="status"
            >
              <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                {uploadFeedback.type === 'success' ? (
                  <CheckCircle2 size={17} style={{ flexShrink: 0, marginTop: 2 }} />
                ) : (
                  <AlertTriangle size={17} style={{ flexShrink: 0, marginTop: 2 }} />
                )}
                <div>
                  <div style={{ fontWeight: 700 }}>{uploadFeedback.title}</div>
                  <div style={{ fontSize: 12.5, marginTop: 2 }}>{uploadFeedback.message}</div>
                  {uploadFeedback.document ? (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 6, fontSize: 12 }}>
                      <span className="mono">
                        SHA-256: {String(getDocHash(uploadFeedback.document)).slice(0, 12)}
                      </span>
                      <span>• Fragmentos: {formatNumber(uploadFeedback.document.chunk_count ?? 0)}</span>
                      <SyncStatusBadge
                        status={getDocSyncStatus(uploadFeedback.document)}
                        errorDetail={getDocSyncDetail(uploadFeedback.document)}
                      />
                    </div>
                  ) : null}
                </div>
              </div>
              <button
                type="button"
                className="btn btn-sm btn-icon"
                onClick={() => setUploadFeedback(null)}
                aria-label="Cerrar notificación"
              >
                <X size={14} />
              </button>
            </div>
          ) : null}

          <div className="form-grid">
            <div className="form-field">
              <label className="form-label" htmlFor="doc-scope">
                Alcance del documento
              </label>
              <select
                id="doc-scope"
                className="select"
                value={scope}
                onChange={(e) => setScope(e.target.value)}
              >
                <option value="SITE">{formatScopeLabel('SITE', siteLabels.singular)}</option>
                <option value="ORGANIZATION">{formatScopeLabel('ORGANIZATION', siteLabels.singular)}</option>
                {isGlobalAdmin ? (
                  <option value="GLOBAL">{formatScopeLabel('GLOBAL', siteLabels.singular)}</option>
                ) : null}
              </select>
            </div>

            <div className="form-field">
              <label className="form-label" htmlFor="doc-site">
                {siteLabels.singular} {scope === 'SITE' ? '*' : '(No aplica para este alcance)'}
              </label>
              <select
                id="doc-site"
                className="select"
                value={scope === 'SITE' ? targetSiteId : ''}
                disabled={scope !== 'SITE'}
                onChange={(e) => setTargetSiteId(e.target.value)}
              >
                <option value="">
                  {scope === 'SITE'
                    ? `Selecciona una ${lowerSingular}...`
                    : formatScopeLabel(scope, siteLabels.singular)}
                </option>
                {scopedSites.map((s) => (
                  <option key={s.site_id} value={s.site_id}>
                    {s.nombre || s.site_name || s.site_id} {s.site_code ? `(${s.site_code})` : ''}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-field">
              <label className="form-label" htmlFor="doc-title">
                Título del documento
              </label>
              <input
                id="doc-title"
                type="text"
                className="input"
                placeholder="ej. Guía de Atención y Horarios 2026"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>

            <div className="form-field">
              <label className="form-label" htmlFor="doc-tags">
                Etiquetas (separadas por coma)
              </label>
              <input
                id="doc-tags"
                type="text"
                className="input"
                placeholder="ej. horarios, politicas, faq"
                value={tagsInput}
                onChange={(e) => setTagsInput(e.target.value)}
              />
            </div>
          </div>

          {uploadMode === 'file' ? (
            <div>
              <input
                ref={fileInputRef}
                type="file"
                accept={ALLOWED_EXTENSIONS.join(',')}
                style={{ display: 'none' }}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleFilePicked(file);
                }}
              />
              <div
                className={`dropzone ${dragActive ? 'dropzone--active' : ''}`}
                role="button"
                tabIndex={0}
                onClick={() => fileInputRef.current?.click()}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    fileInputRef.current?.click();
                  }
                }}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragActive(true);
                }}
                onDragLeave={() => setDragActive(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragActive(false);
                  const file = e.dataTransfer?.files?.[0];
                  if (file) handleFilePicked(file);
                }}
              >
                <UploadCloud size={28} style={{ color: 'var(--accent)' }} />
                {selectedFile ? (
                  <div>
                    <div className="dropzone-title">{selectedFile.name}</div>
                    <div className="dropzone-sub">
                      {formatBytes(selectedFile.size)} • Listo para procesar y guardar
                    </div>
                    <button
                      type="button"
                      className="btn btn-sm"
                      style={{ marginTop: 10 }}
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedFile(null);
                        if (fileInputRef.current) fileInputRef.current.value = '';
                      }}
                    >
                      Quitar archivo
                    </button>
                  </div>
                ) : (
                  <div>
                    <div className="dropzone-title">
                      Arrastra tu documento aquí o haz clic para seleccionar
                    </div>
                    <div className="dropzone-sub">
                      Extensiones: {ALLOWED_EXTENSIONS.join(', ')} • Límite: 15 MB
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="form-grid">
              <div className="form-field form-field--full">
                <label className="form-label" htmlFor="doc-direct-filename">
                  Nombre de referencia del documento
                </label>
                <input
                  id="doc-direct-filename"
                  type="text"
                  className="input mono"
                  value={directFilename}
                  onChange={(e) => setDirectFilename(e.target.value)}
                  style={{ maxWidth: 340 }}
                />
              </div>
              <div className="form-field form-field--full">
                <label className="form-label" htmlFor="doc-direct-text">
                  Contenido del documento ({formatNumber(directText.length)} caracteres)
                </label>
                <textarea
                  id="doc-direct-text"
                  className="textarea mono"
                  placeholder="# Guía de Atención al Usuario&#10;&#10;1. Horarios de servicio..."
                  value={directText}
                  onChange={(e) => setDirectText(e.target.value)}
                />
              </div>
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button type="submit" className="btn btn-primary" disabled={uploading}>
              <FileText size={15} />
              <span>{uploading ? 'Procesando y sincronizando...' : 'Guardar Documento'}</span>
            </button>
          </div>
        </form>
      </section>

      {/* Documents List */}
      <section className="card">
        <div className="table-toolbar">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setOffset(0);
              setAppliedSearch(searchTerm);
            }}
            className="table-toolbar-group"
          >
            <div style={{ position: 'relative', minWidth: 250 }}>
              <Search
                size={15}
                style={{
                  position: 'absolute',
                  left: 10,
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: 'var(--text-muted)',
                }}
              />
              <input
                type="text"
                className="input"
                placeholder="Buscar título, archivo o etiqueta..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                style={{ paddingLeft: 32, height: 34 }}
              />
            </div>

            <select
              className="select"
              value={scopeFilter}
              onChange={(e) => {
                setScopeFilter(e.target.value);
                setOffset(0);
              }}
              style={{ width: 205, height: 34 }}
              aria-label="Filtrar por alcance"
            >
              <option value="ALL">Todos los alcances</option>
              <option value="SITE">{formatScopeLabel('SITE', siteLabels.singular)}</option>
              <option value="ORGANIZATION">{formatScopeLabel('ORGANIZATION', siteLabels.singular)}</option>
              <option value="GLOBAL">{formatScopeLabel('GLOBAL', siteLabels.singular)}</option>
            </select>

            <button type="submit" className="btn btn-sm" style={{ height: 34 }}>
              Filtrar
            </button>
            {appliedSearch ? (
              <button
                type="button"
                className="btn btn-sm"
                style={{ height: 34 }}
                onClick={() => {
                  setSearchTerm('');
                  setAppliedSearch('');
                  setOffset(0);
                }}
              >
                Limpiar
              </button>
            ) : null}
          </form>

          <span className="badge badge--neutral tabular">
            {formatNumber(totalDocs)} documentos totales
          </span>
        </div>

        {docsError ? (
          <div className="card-body">
            <div className="alert alert--error">{docsError}</div>
          </div>
        ) : null}

        <div className="table-wrap">
          {loadingDocs && documents.length === 0 ? (
            <div className="empty-state">
              <span>Cargando documentos del asistente...</span>
            </div>
          ) : documents.length === 0 ? (
            <div className="empty-state">
              <FileText size={26} />
              <span>No hay documentos cargados para los filtros actuales.</span>
            </div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Documento</th>
                  <th>{siteLabels.singular} / Alcance</th>
                  <th className="text-right">Tamaño</th>
                  <th>Huella SHA-256</th>
                  <th className="text-right">Fragmentos</th>
                  <th>Estado</th>
                  <th>Fecha</th>
                  <th className="text-right">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => {
                  const docId = doc.doc_id || doc.id;
                  const fullHash = getDocHash(doc);
                  const shortHash = String(fullHash).slice(0, 10);
                  const siteObj = doc.site_id ? siteMap[doc.site_id] : null;
                  const tags = Array.isArray(doc.tags)
                    ? doc.tags
                    : typeof doc.tags === 'string' && doc.tags
                    ? doc.tags.split(',').map((s) => s.trim())
                    : [];

                  return (
                    <tr key={docId}>
                      <td>
                        <div style={{ fontWeight: 600 }}>{doc.title || doc.filename}</div>
                        <div className="mono" style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>
                          {doc.filename}
                        </div>
                        {tags.length > 0 ? (
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
                            {tags.map((tag) => (
                              <span key={tag} className="badge badge--neutral" style={{ fontSize: 10.5 }}>
                                #{tag}
                              </span>
                            ))}
                          </div>
                        ) : null}
                      </td>
                      <td>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, alignItems: 'flex-start' }}>
                          <ScopeBadge scope={doc.scope} siteLabel={siteLabels.singular} />
                          <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                            {doc.site_id
                              ? siteObj?.nombre || siteObj?.site_name || doc.site_name || doc.site_id
                              : doc.org_name || doc.org_id || 'Plataforma global'}
                          </span>
                        </div>
                      </td>
                      <td className="text-right tabular">
                        {formatBytes(getDocFileSize(doc))}
                      </td>
                      <td>
                        <span className="mono badge badge--neutral" title={fullHash}>
                          {shortHash || '—'}
                        </span>
                      </td>
                      <td className="text-right tabular" style={{ fontWeight: 600 }}>
                        {formatNumber(doc.chunk_count ?? doc.chunks_count ?? 0)}
                      </td>
                      <td>
                        <SyncStatusBadge
                          status={getDocSyncStatus(doc)}
                          errorDetail={getDocSyncDetail(doc)}
                        />
                      </td>
                      <td style={{ fontSize: 12, color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
                        {formatDateTime(doc.created_at || doc.updated_at)}
                      </td>
                      <td className="text-right">
                        <div style={{ display: 'inline-flex', gap: 6, justifyContent: 'flex-end' }}>
                          <button
                            type="button"
                            className="btn btn-sm"
                            onClick={() => handleOpenChunks(doc)}
                            title="Ver fragmentos del documento"
                          >
                            <Eye size={13} />
                            <span>Ver fragmentos</span>
                          </button>
                          <button
                            type="button"
                            className="btn btn-sm"
                            disabled={syncingDocId === docId}
                            onClick={() => handleSyncDoc(doc)}
                            title="Sincronizar con el asistente"
                          >
                            <RefreshCw
                              size={13}
                              className={syncingDocId === docId ? 'spin' : ''}
                            />
                            <span>Sincronizar</span>
                          </button>
                          <button
                            type="button"
                            className="btn btn-sm btn-danger"
                            onClick={() => setDocToDelete(doc)}
                            title="Eliminar documento y sus fragmentos"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        {totalDocs > limit ? (
          <div className="table-toolbar" style={{ borderTop: '1px solid var(--border)', borderBottom: 'none' }}>
            <span style={{ fontSize: 12.5, color: 'var(--text-muted)' }} className="tabular">
              Mostrando {offset + 1} – {Math.min(offset + limit, totalDocs)} de {formatNumber(totalDocs)}
            </span>
            <div style={{ display: 'flex', gap: 6 }}>
              <button
                type="button"
                className="btn btn-sm"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - limit))}
              >
                Anterior
              </button>
              <button
                type="button"
                className="btn btn-sm"
                disabled={offset + limit >= totalDocs}
                onClick={() => setOffset(offset + limit)}
              >
                Siguiente
              </button>
            </div>
          </div>
        ) : null}
      </section>

      {/* Modal: Fragmentos del documento */}
      <Modal
        open={chunksModalOpen}
        wide
        title={
          chunksData?.document
            ? `Fragmentos del documento: ${chunksData.document.title || chunksData.document.filename}`
            : 'Fragmentos del documento'
        }
        onClose={() => setChunksModalOpen(false)}
        footer={
          <button
            type="button"
            className="btn"
            onClick={() => setChunksModalOpen(false)}
          >
            Cerrar
          </button>
        }
      >
        {chunksLoading ? (
          <div className="empty-state">
            <span>Cargando fragmentos del documento...</span>
          </div>
        ) : chunksData ? (
          <>
            <div
              style={{
                display: 'flex',
                flexWrap: 'wrap',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 10,
                paddingBottom: 8,
                borderBottom: '1px solid var(--border)',
              }}
            >
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
                <ScopeBadge scope={chunksData.document?.scope} siteLabel={siteLabels.singular} />
                <SyncStatusBadge
                  status={getDocSyncStatus(chunksData.document)}
                  errorDetail={getDocSyncDetail(chunksData.document)}
                />
                <span className="badge badge--neutral tabular">
                  {(chunksData.chunks || []).length} fragmentos
                </span>
              </div>
              <input
                type="text"
                className="input"
                placeholder="Filtrar texto dentro de fragmentos..."
                value={chunkSearch}
                onChange={(e) => setChunkSearch(e.target.value)}
                style={{ maxWidth: 260, height: 32 }}
              />
            </div>

            {filteredChunks.length === 0 ? (
              <div className="empty-state">
                <FileCode2 size={22} />
                <span>No se encontraron fragmentos con ese criterio.</span>
              </div>
            ) : (
              <div className="chunk-list">
                {filteredChunks.map((chunk, idx) => {
                  const text = chunk.text ?? chunk.content ?? '';
                  const chars = chunk.char_count ?? chunk.chars ?? text.length;
                  const section = chunk.section || chunk.heading || chunk.metadata?.section;
                  const indexLabel = chunk.chunk_index ?? chunk.index ?? idx + 1;
                  return (
                    <div key={chunk.chunk_id || chunk.id || idx} className="chunk-item">
                      <div className="chunk-item-header">
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span className="badge badge--blue tabular">Fragmento #{indexLabel}</span>
                          {section ? (
                            <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                              {section}
                            </span>
                          ) : null}
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span className="tabular" style={{ color: 'var(--text-muted)' }}>
                            {formatNumber(chars)} caracteres
                          </span>
                          <button
                            type="button"
                            className="btn btn-sm"
                            onClick={() => {
                              navigator.clipboard?.writeText(text);
                              if (onToast) onToast('Texto del fragmento copiado.', 'info');
                            }}
                          >
                            <Copy size={12} />
                          </button>
                        </div>
                      </div>
                      <pre className="chunk-item-text">{text}</pre>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        ) : null}
      </Modal>

      {/* Modal: Confirmar Eliminación */}
      <Modal
        open={Boolean(docToDelete)}
        title="Eliminar documento del asistente"
        onClose={() => !deleting && setDocToDelete(null)}
        footer={
          <>
            <button
              type="button"
              className="btn"
              disabled={deleting}
              onClick={() => setDocToDelete(null)}
            >
              Cancelar
            </button>
            <button
              type="button"
              className="btn btn-danger-solid"
              disabled={deleting}
              onClick={handleConfirmDelete}
            >
              {deleting ? 'Eliminando...' : 'Eliminar Definitivamente'}
            </button>
          </>
        }
      >
        {docToDelete ? (
          <div className="alert alert--warning" style={{ flexDirection: 'column' }}>
            <div style={{ fontWeight: 700 }}>
              ¿Confirmas eliminar &quot;{docToDelete.title || docToDelete.filename}&quot;?
            </div>
            <div style={{ fontSize: 13 }}>
              Se eliminarán el registro, sus {formatNumber(docToDelete.chunk_count ?? 0)} fragmentos y su índice en el asistente.
            </div>
          </div>
        ) : null}
      </Modal>
    </div>
  );
}

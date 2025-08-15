from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
import os

router = APIRouter()

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Serve the main dashboard page"""
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Plex Debrid Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        .status-card {
            transition: transform 0.2s;
        }
        .status-card:hover {
            transform: translateY(-2px);
        }
        .loading {
            display: none;
        }
        .error {
            color: #dc3545;
            font-weight: bold;
        }
        .success {
            color: #198754;
            font-weight: bold;
        }
    </style>
</head>
<body class="bg-light">
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="#">
                <i class="fas fa-film me-2"></i>Plex Debrid Dashboard
            </a>
            <button class="btn btn-outline-light" onclick="refreshData()">
                <i class="fas fa-sync-alt"></i> Refresh
            </button>
        </div>
    </nav>

    <div class="container mt-4">
        <!-- Statistics Cards -->
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="card status-card border-warning">
                    <div class="card-body text-center">
                        <i class="fas fa-clock fa-2x text-warning mb-2"></i>
                        <h5 class="card-title">Pending</h5>
                        <h2 id="pending-total" class="text-warning">-</h2>
                        <small class="text-muted">Items waiting to be downloaded</small>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card status-card border-info">
                    <div class="card-body text-center">
                        <i class="fas fa-download fa-2x text-info mb-2"></i>
                        <h5 class="card-title">Downloading</h5>
                        <h2 id="downloading-total" class="text-info">-</h2>
                        <small class="text-muted">Currently downloading</small>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card status-card border-secondary">
                    <div class="card-body text-center">
                        <i class="fas fa-ban fa-2x text-secondary mb-2"></i>
                        <h5 class="card-title">Ignored</h5>
                        <h2 id="ignored-total" class="text-secondary">-</h2>
                        <small class="text-muted">Items in ignore list</small>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card status-card border-success">
                    <div class="card-body text-center">
                        <i class="fas fa-check-circle fa-2x text-success mb-2"></i>
                        <h5 class="card-title">Collected</h5>
                        <h2 id="collected-total" class="text-success">-</h2>
                        <small class="text-muted">Successfully downloaded</small>
                    </div>
                </div>
            </div>
        </div>

        <!-- Navigation Tabs -->
        <ul class="nav nav-tabs" id="mainTabs" role="tablist">
            <li class="nav-item" role="presentation">
                <button class="nav-link active" id="pending-tab" data-bs-toggle="tab" data-bs-target="#pending" type="button" role="tab">
                    <i class="fas fa-clock me-1"></i>Pending Items
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="downloading-tab" data-bs-toggle="tab" data-bs-target="#downloading" type="button" role="tab">
                    <i class="fas fa-download me-1"></i>Downloading
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="ignored-tab" data-bs-toggle="tab" data-bs-target="#ignored" type="button" role="tab">
                    <i class="fas fa-ban me-1"></i>Ignored
                </button>
            </li>
        </ul>

        <!-- Filter Controls -->
        <div class="card mt-3">
            <div class="card-body py-2">
                <div class="row align-items-center">
                    <div class="col">
                        <small class="text-muted">Filter by media type:</small>
                    </div>
                    <div class="col-auto">
                        <div class="btn-group" role="group">
                            <button type="button" class="btn btn-outline-primary btn-sm" onclick="loadCurrentTabItems(null, 1)">All</button>
                            <button type="button" class="btn btn-outline-primary btn-sm" onclick="loadCurrentTabItems('movie', 1)">Movies</button>
                            <button type="button" class="btn btn-outline-primary btn-sm" onclick="loadCurrentTabItems('show', 1)">Shows</button>
                            <button type="button" class="btn btn-outline-primary btn-sm" onclick="loadCurrentTabItems('episode', 1)">Episodes</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Tab Content -->
        <div class="tab-content" id="mainTabsContent">
            <!-- Pending Items Tab -->
            <div class="tab-pane fade show active" id="pending" role="tabpanel">
                <div class="card mt-3">
                    <div class="card-header">
                        <h5 class="mb-0">Pending Items</h5>
                    </div>
                    <div class="card-body">
                        <div id="pending-loading" class="loading text-center">
                            <div class="spinner-border text-primary" role="status">
                                <span class="visually-hidden">Loading...</span>
                            </div>
                        </div>
                        <div id="pending-error" class="error" style="display: none;"></div>
                        <div id="pending-content"></div>
                    </div>
                </div>
            </div>

            <!-- Downloading Items Tab -->
            <div class="tab-pane fade" id="downloading" role="tabpanel">
                <div class="card mt-3">
                    <div class="card-header">
                        <h5 class="mb-0">Currently Downloading</h5>
                    </div>
                    <div class="card-body">
                        <div id="downloading-loading" class="loading text-center">
                            <div class="spinner-border text-info" role="status">
                                <span class="visually-hidden">Loading...</span>
                            </div>
                        </div>
                        <div id="downloading-error" class="error" style="display: none;"></div>
                        <div id="downloading-content"></div>
                    </div>
                </div>
            </div>

            <!-- Ignored Items Tab -->
            <div class="tab-pane fade" id="ignored" role="tabpanel">
                <div class="card mt-3">
                    <div class="card-header">
                        <h5 class="mb-0">Ignored Items</h5>
                    </div>
                    <div class="card-body">
                        <div id="ignored-loading" class="loading text-center">
                            <div class="spinner-border text-secondary" role="status">
                                <span class="visually-hidden">Loading...</span>
                            </div>
                        </div>
                        <div id="ignored-error" class="error" style="display: none;"></div>
                        <div id="ignored-content"></div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Global variables
        let currentTab = 'pending';
        let currentFilter = null;
        let currentPage = 1;
        let currentPageSize = 50;

        // Initialize dashboard
        document.addEventListener('DOMContentLoaded', function() {
            refreshData();
            
            // Add tab change listeners
            document.querySelectorAll('[data-bs-toggle="tab"]').forEach(tab => {
                tab.addEventListener('shown.bs.tab', function(e) {
                    const target = e.target.getAttribute('data-bs-target');
                    if (target === '#pending') {
                        currentTab = 'pending';
                    } else if (target === '#downloading') {
                        currentTab = 'downloading';
                    } else if (target === '#ignored') {
                        currentTab = 'ignored';
                    }
                    // Reset to page 1 when switching tabs
                    currentPage = 1;
                    // Reload current tab with current filter
                    loadCurrentTabItems(currentFilter, 1);
                });
            });
        });

        // Refresh all data
        async function refreshData() {
            await Promise.all([
                loadStatistics(),
                loadPendingItems(),
                loadDownloadingItems(),
                loadIgnoredItems()
            ]);
        }

        // Load items for current tab with optional filter
        async function loadCurrentTabItems(type = null, page = 1) {
            currentFilter = type;
            currentPage = page;
            
            if (currentTab === 'pending') {
                await loadPendingItems(type, page);
            } else if (currentTab === 'downloading') {
                await loadDownloadingItems(type, page);
            } else if (currentTab === 'ignored') {
                await loadIgnoredItems(type, page);
            }
        }

        // Load statistics
        async function loadStatistics() {
            try {
                const response = await fetch('/api/stats');
                const stats = await response.json();
                
                document.getElementById('pending-total').textContent = stats.pending.total;
                document.getElementById('downloading-total').textContent = stats.downloading.total;
                document.getElementById('ignored-total').textContent = stats.ignored.total;
                document.getElementById('collected-total').textContent = stats.collected.total;
            } catch (error) {
                console.error('Error loading statistics:', error);
            }
        }

        // Load pending items
        async function loadPendingItems(type = null, page = 1) {
            const loadingEl = document.getElementById('pending-loading');
            const errorEl = document.getElementById('pending-error');
            const contentEl = document.getElementById('pending-content');
            
            loadingEl.style.display = 'block';
            errorEl.style.display = 'none';
            contentEl.innerHTML = '';
            
            try {
                let url = '/api/pending';
                const params = new URLSearchParams();
                if (type) {
                    params.append('media_type', type);
                }
                params.append('page', page);
                params.append('page_size', currentPageSize);
                
                const response = await fetch(`${url}?${params}`);
                const data = await response.json();
                
                if (data.items && data.items.length > 0) {
                    const table = createItemsTable(data.items, type || 'all');
                    contentEl.appendChild(table);
                    
                    // Add pagination controls
                    if (data.pagination && data.pagination.total_pages > 1) {
                        const paginationEl = createPaginationControls(data.pagination, type);
                        contentEl.appendChild(paginationEl);
                    }
                } else {
                    contentEl.innerHTML = '<div class="text-center text-muted"><i class="fas fa-inbox fa-3x mb-3"></i><p>No pending items found</p></div>';
                }
            } catch (error) {
                errorEl.textContent = 'Error loading pending items: ' + error.message;
                errorEl.style.display = 'block';
            } finally {
                loadingEl.style.display = 'none';
            }
        }

        // Load downloading items
        async function loadDownloadingItems(type = null, page = 1) {
            const loadingEl = document.getElementById('downloading-loading');
            const errorEl = document.getElementById('downloading-error');
            const contentEl = document.getElementById('downloading-content');
            
            loadingEl.style.display = 'block';
            errorEl.style.display = 'none';
            contentEl.innerHTML = '';
            
            try {
                let url = '/api/downloading';
                const params = new URLSearchParams();
                if (type) {
                    params.append('media_type', type);
                }
                params.append('page', page);
                params.append('page_size', currentPageSize);
                
                const response = await fetch(`${url}?${params}`);
                const data = await response.json();
                
                if (data.items && data.items.length > 0) {
                    const table = createItemsTable(data.items, 'downloading');
                    contentEl.appendChild(table);
                    
                    // Add pagination controls
                    if (data.pagination && data.pagination.total_pages > 1) {
                        const paginationEl = createPaginationControls(data.pagination, type);
                        contentEl.appendChild(paginationEl);
                    }
                } else {
                    contentEl.innerHTML = '<div class="text-center text-muted"><i class="fas fa-download fa-3x mb-3"></i><p>No items currently downloading</p></div>';
                }
            } catch (error) {
                errorEl.textContent = 'Error loading downloading items: ' + error.message;
                errorEl.style.display = 'block';
            } finally {
                loadingEl.style.display = 'none';
            }
        }

        // Load ignored items
        async function loadIgnoredItems(type = null, page = 1) {
            const loadingEl = document.getElementById('ignored-loading');
            const errorEl = document.getElementById('ignored-error');
            const contentEl = document.getElementById('ignored-content');
            
            loadingEl.style.display = 'block';
            errorEl.style.display = 'none';
            contentEl.innerHTML = '';
            
            try {
                let url = '/api/ignored';
                const params = new URLSearchParams();
                if (type) {
                    params.append('media_type', type);
                }
                params.append('page', page);
                params.append('page_size', currentPageSize);
                
                const response = await fetch(`${url}?${params}`);
                const data = await response.json();
                
                if (data.items && data.items.length > 0) {
                    const table = createItemsTable(data.items, 'ignored');
                    contentEl.appendChild(table);
                    
                    // Add pagination controls
                    if (data.pagination && data.pagination.total_pages > 1) {
                        const paginationEl = createPaginationControls(data.pagination, type);
                        contentEl.appendChild(paginationEl);
                    }
                } else {
                    contentEl.innerHTML = '<div class="text-center text-muted"><i class="fas fa-ban fa-3x mb-3"></i><p>No ignored items found</p></div>';
                }
            } catch (error) {
                errorEl.textContent = 'Error loading ignored items: ' + error.message;
                errorEl.style.display = 'block';
            } finally {
                loadingEl.style.display = 'none';
            }
        }

        // Create items table
        function createItemsTable(items, type) {
            const table = document.createElement('table');
            table.className = 'table table-striped table-hover';
            
            let headers = ['Title', 'Year', 'Source', 'Added'];
            if (type === 'episode' || items.some(item => item.parent_title)) {
                headers = ['Show', 'Episode', 'Season', 'Source', 'Added'];
            }
            
            const thead = document.createElement('thead');
            const headerRow = document.createElement('tr');
            headers.forEach(header => {
                const th = document.createElement('th');
                th.textContent = header;
                headerRow.appendChild(th);
            });
            thead.appendChild(headerRow);
            table.appendChild(thead);
            
            const tbody = document.createElement('tbody');
            items.forEach(item => {
                const row = document.createElement('tr');
                
                if (type === 'episode' || item.parent_title) {
                    // Episode row
                    row.innerHTML = `
                        <td>${item.grandparent_title || item.parent_title || 'N/A'}</td>
                        <td>${item.title || 'N/A'}</td>
                        <td>${item.parent_index || 'N/A'}</td>
                        <td><span class="badge bg-secondary">${item.watchlisted_by || 'Unknown'}</span></td>
                        <td>${formatDate(item.watchlisted_at || item.updated_at)}</td>
                    `;
                } else {
                    // Movie/Show row
                    row.innerHTML = `
                        <td>${item.title || 'N/A'}</td>
                        <td>${item.year || 'N/A'}</td>
                        <td><span class="badge bg-secondary">${item.watchlisted_by || 'Unknown'}</span></td>
                        <td>${formatDate(item.watchlisted_at || item.updated_at)}</td>
                    `;
                }
                
                tbody.appendChild(row);
            });
            table.appendChild(tbody);
            
            return table;
        }

        // Create pagination controls
        function createPaginationControls(pagination, type) {
            const paginationEl = document.createElement('div');
            paginationEl.className = 'd-flex justify-content-between align-items-center mt-3';
            
            const infoEl = document.createElement('div');
            infoEl.className = 'text-muted small';
            infoEl.textContent = `Showing ${((pagination.page - 1) * pagination.page_size) + 1} to ${Math.min(pagination.page * pagination.page_size, pagination.total_count)} of ${pagination.total_count} items`;
            
            const controlsEl = document.createElement('div');
            controlsEl.className = 'btn-group';
            
            // Previous button
            const prevBtn = document.createElement('button');
            prevBtn.className = 'btn btn-outline-secondary btn-sm';
            prevBtn.innerHTML = '<i class="fas fa-chevron-left"></i> Previous';
            prevBtn.disabled = !pagination.has_prev;
            prevBtn.onclick = () => loadCurrentTabItems(type, pagination.page - 1);
            
            // Next button
            const nextBtn = document.createElement('button');
            nextBtn.className = 'btn btn-outline-secondary btn-sm';
            nextBtn.innerHTML = 'Next <i class="fas fa-chevron-right"></i>';
            nextBtn.disabled = !pagination.has_next;
            nextBtn.onclick = () => loadCurrentTabItems(type, pagination.page + 1);
            
            // Page info
            const pageInfo = document.createElement('span');
            pageInfo.className = 'btn btn-outline-secondary btn-sm disabled';
            pageInfo.textContent = `Page ${pagination.page} of ${pagination.total_pages}`;
            
            controlsEl.appendChild(prevBtn);
            controlsEl.appendChild(pageInfo);
            controlsEl.appendChild(nextBtn);
            
            paginationEl.appendChild(infoEl);
            paginationEl.appendChild(controlsEl);
            
            return paginationEl;
        }

        // Format date
        function formatDate(dateString) {
            if (!dateString) return 'N/A';
            try {
                const date = new Date(dateString);
                return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
            } catch (error) {
                return dateString;
            }
        }
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)

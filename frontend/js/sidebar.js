/**
 * Sidebar.js - Componente de Menú Lateral Estético para Sistema Aula Segura
 * Inyecta una barra lateral moderna, responsiva y colapsable/expandible en modo overlay flotante.
 */
(function() {
    // Detectar página actual
    const currentPage = window.location.pathname.split('/').pop() || 'dashboard.html';
    // Estado colapsado/expandido
    const isCollapsed = localStorage.getItem('sidebar_collapsed') !== 'false';

    // CSS para el Sidebar y ajuste del layout principal
    const style = document.createElement('style');
    style.textContent = `
        :root {
            --sidebar-width: 260px;
            --sidebar-collapsed-width: 72px;
        }
        body {
            background-color: #f8fafc !important;
            min-height: 100vh;
            padding-left: var(--sidebar-width) !important;
            transition: padding-left 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        }
        body.sidebar-collapsed {
            padding-left: var(--sidebar-collapsed-width) !important;
        }
        
        .app-sidebar {
            position: fixed;
            top: 0;
            left: 0;
            height: 100vh;
            width: var(--sidebar-width);
            background: #0f172a;
            color: #f8fafc;
            z-index: 1000;
            display: flex;
            flex-direction: column;
            box-shadow: 6px 0 28px rgba(0,0,0,0.25);
            transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1), transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .app-sidebar.collapsed {
            width: var(--sidebar-collapsed-width);
            box-shadow: 2px 0 12px rgba(0,0,0,0.1);
        }

        /* BRAND / CABECERA */
        .app-sidebar-brand {
            padding: 1.25rem 1rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid rgba(255,255,255,0.08);
            background: linear-gradient(135deg, #1e1b4b 0%, #0f172a 100%);
            overflow: hidden;
            height: 64px;
            box-sizing: border-box;
        }
        .app-sidebar.collapsed .app-sidebar-brand {
            justify-content: center;
            padding: 1rem 0;
        }
        .app-sidebar-brand-info {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            overflow: hidden;
        }
        .app-sidebar.collapsed .app-sidebar-brand-info {
            justify-content: center;
            width: 100%;
            cursor: pointer;
        }
        .app-sidebar-logo {
            width: 38px;
            height: 38px;
            min-width: 38px;
            background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #ffffff;
            font-weight: 800;
            box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        .app-sidebar.collapsed .app-sidebar-logo:hover {
            transform: scale(1.08);
            box-shadow: 0 6px 16px rgba(99, 102, 241, 0.6);
        }
        .app-sidebar-brand-text {
            display: flex;
            flex-direction: column;
            white-space: nowrap;
            transition: opacity 0.2s ease;
        }
        .app-sidebar.collapsed .app-sidebar-brand-text {
            display: none !important;
        }
        
        /* Botón contraer/expandir */
        .sidebar-toggle-btn {
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.12);
            color: #94a3b8;
            width: 28px;
            height: 28px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            font-size: 0.75rem;
            transition: all 0.2s ease;
            flex-shrink: 0;
        }
        .app-sidebar.collapsed .sidebar-toggle-btn {
            display: flex !important;
        }
        .sidebar-toggle-btn:hover {
            background: #6366f1;
            color: #ffffff;
            border-color: #6366f1;
            box-shadow: 0 2px 8px rgba(99, 102, 241, 0.4);
        }

        /* MENÚ */
        .app-sidebar-menu {
            flex: 1;
            overflow-y: auto;
            padding: 1rem 0.5rem;
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
        }
        .app-sidebar-heading {
            font-size: 0.68rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #64748b;
            padding: 0.75rem 0.75rem 0.25rem 0.75rem;
            white-space: nowrap;
        }
        .app-sidebar.collapsed .app-sidebar-heading {
            display: none !important;
        }

        .app-sidebar-link {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            padding: 0.7rem 0.85rem;
            border-radius: 8px;
            color: #94a3b8;
            font-size: 0.88rem;
            font-weight: 500;
            text-decoration: none;
            transition: all 0.2s ease;
            white-space: nowrap;
            position: relative;
        }
        .app-sidebar.collapsed .app-sidebar-link {
            justify-content: center;
            padding: 0.7rem 0;
        }
        .app-sidebar-link:hover {
            background: rgba(255, 255, 255, 0.06);
            color: #f1f5f9;
        }
        .app-sidebar-link.active {
            background: linear-gradient(135deg, #4f46e5 0%, #4338ca 100%);
            color: #ffffff;
            font-weight: 600;
            box-shadow: 0 4px 14px rgba(79, 70, 229, 0.35);
        }
        .app-sidebar-icon {
            width: 22px;
            height: 22px;
            min-width: 22px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.1rem;
        }
        .app-sidebar.collapsed .app-sidebar-link span:not(.app-sidebar-icon) {
            display: none !important;
        }

        /* FOOTER / USUARIO */
        .app-sidebar-footer {
            padding: 0.85rem;
            border-top: 1px solid rgba(255,255,255,0.08);
            background: #090d16;
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
            overflow: hidden;
        }
        .app-sidebar-user {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }
        .app-sidebar.collapsed .app-sidebar-user {
            justify-content: center;
        }
        .app-sidebar-avatar {
            width: 38px;
            height: 38px;
            min-width: 38px;
            border-radius: 50%;
            background: linear-gradient(135deg, #818cf8 0%, #6366f1 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            color: #ffffff;
            font-weight: 700;
            font-size: 0.95rem;
        }
        .app-sidebar-user-details {
            display: flex;
            flex-direction: column;
            truncate: true;
            white-space: nowrap;
        }
        .app-sidebar.collapsed .app-sidebar-user-details,
        .app-sidebar.collapsed .app-sidebar-footer-buttons {
            display: none !important;
        }
        
        /* Ajuste responsivo para móvil */
        @media (min-width: 1024px) {
            .mobile-header {
                display: none !important;
            }
        }
        @media (max-width: 1023px) {
            .app-sidebar {
                transform: translateX(-100%);
                width: 260px !important;
            }
            .app-sidebar.open {
                transform: translateX(0);
            }
            body {
                padding-left: 0 !important;
                padding-top: 60px !important;
            }
            .mobile-header {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                height: 60px;
                background: #0f172a;
                color: #fff;
                z-index: 999;
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 0 1.25rem;
                box-shadow: 0 2px 10px rgba(0,0,0,0.15);
            }
            .sidebar-toggle-btn {
                display: none !important;
            }
        }
    `;
    document.head.appendChild(style);

    // Ocultar header original si existe para evitar duplicados
    window.addEventListener('DOMContentLoaded', () => {
        const oldHeader = document.querySelector('header');
        if (oldHeader && !oldHeader.classList.contains('mobile-header')) {
            oldHeader.style.display = 'none';
        }
        renderSidebar();
        if (isCollapsed) {
            document.body.classList.add('sidebar-collapsed');
        } else {
            document.body.classList.remove('sidebar-collapsed');
        }
    });

    function renderSidebar() {
        if (document.getElementById('app-sidebar-root')) return;

        const role = localStorage.getItem('role') || 'viewer';
        const userName = localStorage.getItem('userName') || 'Usuario';
        const isLawyer = role === 'lawyer' || role === 'admin';
        const isAdmin = role === 'admin';

        // Contenedor Sidebar HTML
        const sidebarHTML = `
            <!-- Header Móvil -->
            <div class="mobile-header">
                <div class="flex items-center gap-3">
                    <button onclick="toggleMobileSidebar()" class="text-white text-2xl focus:outline-none">
                        ☰
                    </button>
                    <div class="flex items-center gap-2">
                        <span class="font-bold text-white text-sm">Aula Segura</span>
                    </div>
                </div>
                <div class="flex items-center gap-2">
                    <span class="text-xs bg-indigo-500/20 text-indigo-300 font-bold px-2 py-0.5 rounded border border-indigo-500/30 uppercase">${role}</span>
                </div>
            </div>

            <!-- Overlay Móvil -->
            <div id="sidebar-overlay" onclick="toggleMobileSidebar()" class="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[999] hidden lg:hidden"></div>

            <!-- Sidebar Principal -->
            <aside id="app-sidebar-root" class="app-sidebar ${isCollapsed ? 'collapsed' : ''}">
                <div class="app-sidebar-brand">
                    <div class="app-sidebar-brand-info" onclick="if(document.getElementById('app-sidebar-root')?.classList.contains('collapsed')) toggleDesktopSidebar()" title="Desplegar Menú">
                        <div class="app-sidebar-logo">🛡️</div>
                        <div class="app-sidebar-brand-text">
                            <span class="font-extrabold text-white text-base tracking-wide">Aula Segura</span>
                            <span class="text-[10px] text-indigo-300 font-medium tracking-wider uppercase">Colegios de Chile</span>
                        </div>
                    </div>
                    <button id="sidebar-toggle-btn" onclick="toggleDesktopSidebar()" class="sidebar-toggle-btn" title="${isCollapsed ? 'Expandir Menú' : 'Contraer Menú'}">
                        ${isCollapsed ? '▶' : '◀'}
                    </button>
                </div>

                <div class="app-sidebar-menu">
                    <div class="app-sidebar-heading">Navegación Aula Segura</div>
                    
                    <a href="dashboard.html" title="Listado Alumnos" class="app-sidebar-link ${currentPage === 'dashboard.html' ? 'active' : ''}">
                        <span class="app-sidebar-icon">📊</span>
                        <span>Listado Alumnos</span>
                    </a>

                    ${isLawyer ? `
                    <a href="registro.html" title="Nuevo Alumno" class="app-sidebar-link ${currentPage === 'registro.html' ? 'active' : ''}">
                        <span class="app-sidebar-icon">➕</span>
                        <span>Nuevo Alumno</span>
                    </a>
                    ` : ''}

                    <div class="app-sidebar-heading mt-3">Otras Medidas</div>

                    <a href="otras_medidas.html" title="Otras Medidas" class="app-sidebar-link ${currentPage === 'otras_medidas.html' ? 'active' : ''}">
                        <span class="app-sidebar-icon">📋</span>
                        <span>Otras Medidas</span>
                    </a>

                    ${isLawyer ? `
                    <a href="registro_otras_medidas.html" title="Registrar Medida" class="app-sidebar-link ${currentPage === 'registro_otras_medidas.html' ? 'active' : ''}">
                        <span class="app-sidebar-icon">📝</span>
                        <span>Registrar Medida</span>
                    </a>
                    ` : ''}

                    <div class="app-sidebar-heading mt-3">Configuración</div>

                    <a href="destinatarios.html" title="Destinatarios y Grupos" class="app-sidebar-link ${currentPage === 'destinatarios.html' ? 'active' : ''}">
                        <span class="app-sidebar-icon">👥</span>
                        <span>Destinatarios y Grupos</span>
                    </a>

                    <a href="correos_programados.html" title="Correos Programados" class="app-sidebar-link ${currentPage === 'correos_programados.html' ? 'active' : ''}">
                        <span class="app-sidebar-icon">📬</span>
                        <span>Correos Programados</span>
                    </a>

                    <a href="plantillas.html" title="Plantillas y Plazos" class="app-sidebar-link ${currentPage === 'plantillas.html' ? 'active' : ''}">
                        <span class="app-sidebar-icon">📧</span>
                        <span>Plantillas y Plazos</span>
                    </a>

                    ${isLawyer ? `
                    <a href="upload.html" title="Carga Masiva Excel" class="app-sidebar-link ${currentPage === 'upload.html' ? 'active' : ''}">
                        <span class="app-sidebar-icon">📤</span>
                        <span>Carga Masiva Excel</span>
                    </a>
                    ` : ''}

                    ${isAdmin ? `
                    <a href="admin.html" title="Usuarios y Permisos" class="app-sidebar-link ${currentPage === 'admin.html' ? 'active' : ''}">
                        <span class="app-sidebar-icon">👥</span>
                        <span>Usuarios y Permisos</span>
                    </a>
                    ` : ''}
                </div>

                <div class="app-sidebar-footer">
                    <div class="app-sidebar-user">
                        <div class="app-sidebar-avatar" title="${userName}">${(userName[0] || 'U').toUpperCase()}</div>
                        <div class="app-sidebar-user-details truncate">
                            <span class="text-sm font-bold text-white truncate" id="sidebar-user-name">${userName}</span>
                            <span class="text-xs text-indigo-400 font-semibold uppercase">${role}</span>
                        </div>
                    </div>
                    <div class="app-sidebar-footer-buttons flex gap-2 pt-1 border-t border-slate-800">
                        <button onclick="if(window.openPassModal) openPassModal(); else alert('Acción disponible en panel');" class="flex-1 text-xs py-1.5 px-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded font-medium transition text-center">
                            🔑 Clave
                        </button>
                        <button onclick="logout()" class="text-xs py-1.5 px-3 bg-red-500/20 hover:bg-red-500/30 text-red-300 border border-red-500/30 rounded font-bold transition">
                            Salir
                        </button>
                    </div>
                </div>
            </aside>
        `;

        const div = document.createElement('div');
        div.innerHTML = sidebarHTML;
        document.body.appendChild(div);
    }

    window.toggleDesktopSidebar = function() {
        const sidebar = document.getElementById('app-sidebar-root');
        if (!sidebar) return;

        const isNowCollapsed = sidebar.classList.toggle('collapsed');
        document.body.classList.toggle('sidebar-collapsed', isNowCollapsed);

        const toggleBtn = document.getElementById('sidebar-toggle-btn');
        if (toggleBtn) {
            toggleBtn.innerText = isNowCollapsed ? '▶' : '◀';
            toggleBtn.title = isNowCollapsed ? 'Expandir Menú' : 'Contraer Menú';
        }

        localStorage.setItem('sidebar_collapsed', isNowCollapsed ? 'true' : 'false');
    };

    window.toggleMobileSidebar = function() {
        const sidebar = document.getElementById('app-sidebar-root');
        const overlay = document.getElementById('sidebar-overlay');
        if (sidebar) sidebar.classList.toggle('open');
        if (overlay) overlay.classList.toggle('hidden');
    };

    window.logout = function() {
        localStorage.removeItem('token');
        localStorage.removeItem('role');
        localStorage.removeItem('userName');
        window.location.href = 'index.html';
    };
})();

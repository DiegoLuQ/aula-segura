const API_URL = isLocal ? 'http://127.0.0.1:8000' : window.location.origin;
let currentUser = null;

// Initialization
document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
    loadColegios();
});

// Authentication
async function checkAuth() {
    const token = localStorage.getItem('token');
    if (!token) {
        showSection('login-section');
        return;
    }

    try {
        const response = await fetch(`${API_URL}/me`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (response.ok) {
            currentUser = await response.json();
            setupDashboard();
            loadStudents();
        } else {
            logout();
        }
    } catch (e) {
        console.error('Auth error', e);
        logout();
    }
}

document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const nombre = document.getElementById('username').value;
    const clave = document.getElementById('password').value;
    const errorEl = document.getElementById('login-error');

    try {
        const response = await fetch(`${API_URL}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nombre, clave })
        });

        if (response.ok) {
            const data = await response.json();
            localStorage.setItem('token', data.access_token);
            checkAuth();
        } else {
            const err = await response.json();
            errorEl.innerText = err.detail || 'Error al iniciar sesión';
            errorEl.classList.remove('hidden');
        }
    } catch (e) {
        errorEl.innerText = 'No se pudo conectar con el servidor';
        errorEl.classList.remove('hidden');
    }
});

function logout() {
    localStorage.removeItem('token');
    currentUser = null;
    showSection('login-section');
}

// UI Management
function showSection(id) {
    document.getElementById('login-section').classList.add('hidden');
    document.getElementById('dashboard-section').classList.add('hidden');
    document.getElementById(id).classList.remove('hidden');
}

function setupDashboard() {
    showSection('dashboard-section');
    document.getElementById('user-info').innerText = currentUser.nombre;
    document.getElementById('user-role-badge').innerText = currentUser.rol;

    if (currentUser.rol === 'lawyer') {
        document.getElementById('btn-add-student').classList.remove('hidden');
    } else {
        document.getElementById('btn-add-student').classList.add('hidden');
    }
}

function toggleModal(id, show) {
    const modal = document.getElementById(id);
    if (show) {
        modal.classList.remove('hidden');
    } else {
        modal.classList.add('hidden');
        document.getElementById('student-form').reset();
        document.getElementById('student-id').value = '';
    }
}

// Data Loading
async function loadStudents() {
    const token = localStorage.getItem('token');
    const tbody = document.getElementById('students-table-body');
    const loading = document.getElementById('loading-state');
    const empty = document.getElementById('empty-state');

    loading.classList.remove('hidden');
    tbody.innerHTML = '';

    try {
        const response = await fetch(`${API_URL}/estudiantes`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const students = await response.json();

        loading.classList.add('hidden');
        if (students.length === 0) {
            empty.classList.remove('hidden');
            return;
        }
        empty.classList.add('hidden');

        students.forEach(s => {
            const tr = document.createElement('tr');
            tr.className = 'hover:bg-slate-50 transition';
            tr.innerHTML = `
                <td class="px-4 py-4 font-medium">${s.nombre_estudiante}</td>
                <td class="px-4 py-4 text-slate-500">${s.curso}</td>
                <td class="px-4 py-4 text-slate-500 max-w-xs truncate">${s.causa}</td>
                <td class="px-4 py-4 text-slate-500">${s.resultado_revision || '-'}</td>
                <td class="px-4 py-4">
                    <span class="px-2 py-1 ${s.medida === 'EXPULSIÓN' ? 'bg-red-50 text-red-700' : 'bg-amber-50 text-amber-700'} text-[10px] font-bold rounded">
                        ${s.medida}
                    </span>
                </td>
                <td class="px-4 py-4 text-right">
                    ${currentUser.rol === 'lawyer' ? `
                        <button onclick="editStudent(${JSON.stringify(s).replace(/"/g, '&quot;')})" class="text-indigo-600 hover:text-indigo-900 font-bold">Editar</button>
                    ` : '<span class="text-slate-300 italic">Solo lectura</span>'}
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        loading.innerText = 'Error al cargar datos';
    }
}

async function loadColegios() {
    try {
        const response = await fetch(`${API_URL}/colegios`);
        const colegios = await response.json();
        const select = document.getElementById('f-colegio');
        select.innerHTML = colegios.map(c => `<option value="${c.id}">${c.nombre}</option>`).join('');
    } catch (e) { console.error('Error loading colegios', e); }
}

// Student Operations
document.getElementById('student-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const token = localStorage.getItem('token');
    const id = document.getElementById('student-id').value;

    const payload = {
        nombre_estudiante: document.getElementById('f-nombre').value,
        curso: document.getElementById('f-curso').value,
        causa: document.getElementById('f-causa').value,
        id_colegio: parseInt(document.getElementById('f-colegio').value),
        fecha_inicio_proceso: document.getElementById('f-fecha-inicio').value || null,
        fecha_notificacion_medida: document.getElementById('f-fecha-notif').value || null,
        descargos: document.getElementById('f-descargos').value,
        medida: document.getElementById('f-medida').value,
        resultado_revision: document.getElementById('f-resultado').value
    };

    const method = id ? 'PUT' : 'POST';
    const url = id ? `${API_URL}/estudiantes/${id}` : `${API_URL}/estudiantes`;

    try {
        const response = await fetch(url, {
            method,
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            toggleModal('modal-student', false);
            loadStudents();
        } else {
            alert('Error al guardar el registro');
        }
    } catch (e) {
        alert('Error de conexión');
    }
});

function editStudent(s) {
    document.getElementById('modal-title').innerText = 'Editar Registro';
    document.getElementById('student-id').value = s.id;
    document.getElementById('f-nombre').value = s.nombre_estudiante;
    document.getElementById('f-curso').value = s.curso;
    document.getElementById('f-causa').value = s.causa;
    document.getElementById('f-colegio').value = s.id_colegio;
    document.getElementById('f-fecha-inicio').value = s.fecha_inicio_proceso || '';
    document.getElementById('f-fecha-notif').value = s.fecha_notificacion_medida || '';
    document.getElementById('f-descargos').value = s.descargos || '';
    document.getElementById('f-medida').value = s.medida || 'EXPULSIÓN';
    document.getElementById('f-resultado').value = s.resultado_revision || '';

    toggleModal('modal-student', true);
}

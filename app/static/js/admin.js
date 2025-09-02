function showMessage(message, type) {
    const messageArea = document.getElementById('message-area');
    const className = type === 'success' ? 'success-message' : 'error-message';
    messageArea.innerHTML = `<div class="${className}" style="display: block;">${message}</div>`;
    setTimeout(() => { messageArea.innerHTML = ''; }, 5000);
}

/**
 * Função genérica para preencher uma tabela com dados.
 * @param {string} tbodyId - O ID do corpo da tabela (tbody).
 * @param {Array} data - O array de objetos com os dados.
 * @param {Function} rowTemplate - Uma função que recebe um item de dados e retorna o HTML para as células (td).
 * @param {number} colCount - O número de colunas da tabela.
 */
function populateTable(tbodyId, data, rowTemplate, colCount) {
    const tbody = document.getElementById(tbodyId);
    tbody.innerHTML = '';
    if (!data || data.length === 0) {
        tbody.innerHTML = `<tr><td colspan="${colCount}" style="text-align: center;">Nenhum registro encontrado</td></tr>`;
        return;
    }
    data.forEach(entry => {
        const row = document.createElement('tr');
        row.innerHTML = rowTemplate(entry);
        tbody.appendChild(row);
    });
}

function loadAccessLog() {
    fetch('/admin/access-log')
    .then(response => {
        if (response.status === 401) {
            adminLogout();
            throw new Error('Não autorizado');
        }
        return response.json();
    })
    .then(data => {
        if (data.error) {
            showMessage(data.error, 'error');
            return;
        }
        
        populateTable('access-log-body', data.raw_logs, entry => `
            <td>${entry.username}</td>
            <td>${entry.timestamp}</td>
            <td>${entry.ip || 'N/A'}</td>
        `, 3);

        populateTable('unique-logins-body', data.unique_by_day, entry => `
            <td>${entry.date}</td>
            <td>${entry.unique_count}</td>
        `, 2);

        populateTable('repeated-logins-body', data.repeated_logins, entry => `
            <td>${entry.username}</td>
            <td>${entry.count}</td>
        `, 2);
        
        // NOVA CHAMADA PARA PREENCHER A TABELA DE HORÁRIOS
        populateTable('top-hours-body', data.top_access_hours, entry => `
            <td>${entry.hour_range}</td>
            <td>${entry.count}</td>
        `, 2);
    })
    .catch(error => {
        if (error.message !== 'Não autorizado') {
            showMessage('Erro ao carregar registros de acesso', 'error');
        }
    });
}

function adminLogin() {
    const username = document.getElementById('admin-username').value;
    const password = document.getElementById('admin-password').value;
    const errorDiv = document.getElementById('login-error');
    
    if (!username || !password) {
        errorDiv.textContent = 'Por favor, preencha todos os campos';
        errorDiv.style.display = 'block';
        return;
    }
    
    fetch('/admin/loginadmin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            document.getElementById('login-form').style.display = 'none';
            document.getElementById('admin-panel').style.display = 'block';
            loadAccessLog();
        } else {
            errorDiv.textContent = data.message || 'Erro no login';
            errorDiv.style.display = 'block';
        }
    })
    .catch(error => {
        errorDiv.textContent = 'Erro de conexão';
        errorDiv.style.display = 'block';
    });
}

function clearAccessLog() {
    if (!confirm('Tem certeza que deseja limpar todos os registros de acesso? Esta ação não pode ser desfeita.')) {
        return;
    }
    fetch('/admin/clear-log', { method: 'POST' })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showMessage('Registros limpos com sucesso', 'success');
            loadAccessLog();
        } else {
            showMessage(data.error || 'Erro ao limpar registros', 'error');
        }
    })
    .catch(() => showMessage('Erro ao limpar registros', 'error'));
}

function adminLogout() {
    fetch('/admin/logout')
    .then(() => {
        document.getElementById('login-form').style.display = 'block';
        document.getElementById('admin-panel').style.display = 'none';
        document.getElementById('admin-username').value = '';
        document.getElementById('admin-password').value = '';
    })
    .catch(error => console.error('Erro no logout:', error));
}

document.addEventListener('DOMContentLoaded', function() {
    const loginButton = document.querySelector('#login-form button');
    if (loginButton) {
        loginButton.addEventListener('click', adminLogin);
    }
    // Botão para Limpar Registros
    const clearButton = document.getElementById('clear-log-btn');
    if (clearButton) {
        clearButton.addEventListener('click', clearAccessLog);
    }

    // Botão para Sair (Logout)
    const logoutButton = document.getElementById('logout-btn');
    if (logoutButton) {
        logoutButton.addEventListener('click', adminLogout);
    }
    fetch('/admin/access-log')
    .then(response => {
        if (response.ok) return response.json();
        throw new Error('Não autorizado');
    })
    .then(data => {
        document.getElementById('login-form').style.display = 'none';
        document.getElementById('admin-panel').style.display = 'block';
        loadAccessLog();
    })
    .catch(error => console.log('Usuário não autenticado:', error.message));
});
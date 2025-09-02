document.addEventListener('DOMContentLoaded', function() {
    const loginForm = document.getElementById('login-form');
    
    if (loginForm) {
        loginForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const usernameInput = document.getElementById('username');
            const username = usernameInput.value.trim();
            const submitBtn = document.querySelector('.btn-primary');
            const originalBtnText = submitBtn.textContent;
            
            if (!username) {
                showError('Please enter your Sleeper username');
                return;
            }
            
            try {
                // Mostrar estado de carregamento
                submitBtn.disabled = true;
                submitBtn.textContent = 'Signing in...';
                
                const response = await fetch('/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ username })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    // Redirecionar para dashboard após login bem-sucedido
                    window.location.href = '/dashboard';
                } else {
                    showError(result.message || 'Login failed. Please try again.');
                }
            } catch (error) {
                showError('Network error. Please check your connection and try again.');
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = originalBtnText;
            }
        });
    }
    
    function showError(message) {
        const errorDiv = document.querySelector('.error-message');
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
        
        // Ocultar automaticamente após 5 segundos
        setTimeout(() => {
            errorDiv.style.display = 'none';
        }, 5000);
    }
    
    // Verificar se o usuário já está logado
    async function checkLoginStatus() {
        try {
            const response = await fetch('/check-login');
            const data = await response.json();
            
            if (data.logged_in) {
                window.location.href = '/dashboard';
            }
        } catch (error) {
            console.error('Error checking login status:', error);
        }
    }
    
    checkLoginStatus();
});
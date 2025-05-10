// Auto-refresh evaluation page
function startPolling() {
    setInterval(function() {
        window.location.reload();
    }, 3000); // Refresh every 3 seconds
}

// Start evaluation function
function startEvaluation(hackathonId) {
    const button = document.getElementById('startEvaluation');
    if (!button) return;
    
    // Disable button and show loading
    button.disabled = true;
    button.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Evaluating...';
    
    // Send request
    fetch(`/start_evaluation/${hackathonId}`)
        .then(response => response.json())
        .then(data => {
            if (data.status === 'started') {
                // Start polling for updates
                startPolling();
                
                // Show success message
                const alertDiv = document.createElement('div');
                alertDiv.className = 'alert alert-success alert-dismissible fade show';
                alertDiv.innerHTML = `
                    <strong>Success!</strong> Evaluation has started. Page will auto-refresh.
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                `;
                document.querySelector('.container').insertBefore(alertDiv, document.querySelector('h2').nextSibling);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            button.disabled = false;
            button.textContent = 'Start Evaluation';
        });
}

// Landing page animation
document.addEventListener('DOMContentLoaded', function() {
    const logo = document.querySelector('.logo-animation');
    if (logo) {
        logo.classList.add('animate');
    }
});

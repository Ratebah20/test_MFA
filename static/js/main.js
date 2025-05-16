/**
 * Script principal pour la simulation Selfcare
 * Ce fichier contient les fonctionnalités JavaScript communes à toutes les pages
 */

document.addEventListener('DOMContentLoaded', function() {
    // Ajouter l'année courante au footer
    const footerYear = document.querySelector('.footer-container p');
    if (footerYear) {
        const currentYear = new Date().getFullYear();
        footerYear.innerHTML = footerYear.innerHTML.replace('{{ now.year }}', currentYear);
    }
    
    // Gestion des messages flash
    const flashMessages = document.querySelectorAll('.flash-message');
    flashMessages.forEach(message => {
        // Ajouter un bouton de fermeture
        const closeButton = document.createElement('button');
        closeButton.innerHTML = '&times;';
        closeButton.className = 'close-btn';
        closeButton.addEventListener('click', function() {
            message.style.opacity = '0';
            setTimeout(() => {
                message.remove();
            }, 300);
        });
        
        message.appendChild(closeButton);
        
        // Auto-fermer après 5 secondes
        setTimeout(() => {
            message.style.opacity = '0';
            setTimeout(() => {
                message.remove();
            }, 300);
        }, 5000);
    });
    
    // Fonction utilitaire pour extraire les paramètres d'URL
    window.getUrlParams = function() {
        const params = {};
        const queryString = window.location.search;
        const urlParams = new URLSearchParams(queryString);
        
        for (const [key, value] of urlParams) {
            params[key] = value;
        }
        
        return params;
    };
    
    // Fonction utilitaire pour formater un token OTP (masquer partiellement)
    window.formatOtpToken = function(token) {
        if (!token || token.length < 10) {
            return token;
        }
        
        const prefix = token.substring(0, 5);
        const suffix = token.substring(token.length - 5);
        return `${prefix}...${suffix}`;
    };
    
    // Détecter la présence d'un token OTP dans l'URL
    const urlParams = window.getUrlParams();
    if (urlParams.otp_token) {
        console.log('Token OTP détecté dans l\'URL:', formatOtpToken(urlParams.otp_token));
    }
});

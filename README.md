# Simulation d'intégration Selfcare avec OTP

Ce projet simule une intégration entre le Portail Orange (système MFA) et une application externe (Selfcare) en utilisant la méthode OTP. Il a été créé pour tester et démontrer le processus de redirection et validation des tokens OTP conformément à la documentation technique.

## Fonctionnalités

- Simulation de redirection depuis le Portail Orange avec un token OTP
- Validation des tokens OTP via API
- Simulation du dashboard après authentification réussie
- Gestion des cas particuliers (première connexion avec changement de mot de passe)
- Simulation des scénarios d'erreur (token invalide, expiré, etc.)

## Prérequis

- Python 3.8+
- pip (gestionnaire de paquets Python)

## Installation locale

1. Clonez le dépôt :
   ```
   git clone [URL_DU_REPO]
   cd simulation_SELFcare
   ```

2. Créez et activez un environnement virtuel (optionnel mais recommandé) :
   ```
   python -m venv venv
   venv\Scripts\activate  # Windows
   source venv/bin/activate  # Linux/Mac
   ```

3. Installez les dépendances :
   ```
   pip install -r requirements.txt
   ```

4. Lancez l'application :
   ```
   python app.py
   ```

5. Accédez à l'application dans votre navigateur à l'adresse `http://localhost:5000`

## Configuration

L'application peut être configurée à l'aide de variables d'environnement :

- `PORT` : Port sur lequel l'application s'exécute (par défaut : 5000)
- `MOCK_API` : Simule les réponses API sans appeler le serveur réel (`true` ou `false`, par défaut : `true`)
- `PORTAIL_API_URL` : URL de l'API du Portail Orange (par défaut : `https://acc.portail.orange.lu`)

## Déploiement sur Render

1. Créez un nouveau service Web sur Render
2. Connectez votre dépôt Git
3. Configurez les paramètres suivants :
   - **Name** : `selfcare-otp-simulation` (ou autre nom de votre choix)
   - **Environment** : `Python 3`
   - **Build Command** : `pip install -r requirements.txt`
   - **Start Command** : `gunicorn app:app`
4. Ajoutez les variables d'environnement nécessaires
5. Cliquez sur "Create Web Service"

## Cas d'utilisation

### 1. Simulation d'une redirection valide

1. Visitez la page d'accueil
2. Cliquez sur "Simuler une redirection avec OTP"
3. Vous serez redirigé avec un token OTP valide
4. La validation s'effectue et vous accédez au dashboard

### 2. Simulation d'une première connexion

1. Visitez la page d'accueil
2. Cliquez sur "Simuler une première connexion"
3. Vous serez redirigé vers la page de changement de mot de passe
4. Définissez un mot de passe conforme aux exigences
5. Accédez au dashboard après validation

### 3. Simulation de scénarios d'erreur

Depuis la page de connexion, choisissez l'une des options suivantes :
- "Simuler une redirection avec OTP invalide"
- "Simuler une redirection avec OTP expiré"

## Structure du projet

```
simulation_SELFcare/
├── app.py                # Application principale Flask
├── requirements.txt      # Dépendances Python
├── static/               # Fichiers statiques (CSS, JS, images)
│   ├── css/              # Feuilles de style
│   ├── js/               # Scripts JavaScript
│   └── img/              # Images et icônes
└── templates/            # Templates HTML
    ├── base.html         # Template de base
    ├── index.html        # Page d'accueil
    ├── login.html        # Page de connexion
    ├── dashboard.html    # Dashboard
    ├── processing.html   # Page de traitement OTP
    ├── error.html        # Page d'erreur
    └── ...               # Autres templates
```

## Documentation associée

Ce simulateur a été créé en se basant sur les documents suivants :
- Guide d'intégration OTP (`OTP_INTEGRATION_GUIDE.md`)
- Spécifications techniques OTP (`OTP_TECHNICAL_SPECS.md`)
- Guide d'intégration Selfcare (`SELFCARE_INTEGRATION.md`)

## Contribuer

Pour contribuer à ce projet :
1. Créez une branche (`git checkout -b feature/nouvelle-fonctionnalite`)
2. Effectuez vos modifications
3. Committez vos changements (`git commit -m 'Ajout d'une nouvelle fonctionnalité'`)
4. Poussez vers la branche (`git push origin feature/nouvelle-fonctionnalite`)
5. Ouvrez une Pull Request

## Licence

Ce projet est destiné à des fins de test et de démonstration uniquement.

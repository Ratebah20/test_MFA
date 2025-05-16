# Guide de déploiement sur Render

Ce guide vous explique comment déployer votre application d'intégration Selfcare avec OTP sur Render.com.

## Prérequis

- Un compte sur [Render.com](https://render.com)
- Votre code source sur GitHub (déjà fait)

## Étapes de déploiement

1. **Se connecter à Render**
   - Accédez à [dashboard.render.com](https://dashboard.render.com) et connectez-vous à votre compte

2. **Créer un nouveau service Web**
   - Cliquez sur "New" puis sélectionnez "Web Service"

3. **Connecter votre dépôt GitHub**
   - Choisissez "Connect GitHub"
   - Autorisez Render à accéder à vos dépôts
   - Sélectionnez le dépôt `test_MFA`

4. **Configurer le service**
   - **Name** : `selfcare-otp-integration` (ou autre nom de votre choix)
   - **Environment** : `Python 3`
   - **Region** : Choisissez la région la plus proche de vos utilisateurs
   - **Branch** : `main`
   - **Build Command** : `pip install -r requirements.txt`
   - **Start Command** : `gunicorn app:app`

5. **Configurer les variables d'environnement (optionnel)**
   - Cliquez sur "Advanced" puis "Add Environment Variable"
   - Variables à considérer :
     - `MOCK_API` : `false` (pour utiliser les vraies API)
     - `PORTAIL_API_URL` : `https://acc.portail.orange.lu`
     - `SECRET_KEY` : Générez une valeur aléatoire pour la sécurité

6. **Finalisez le déploiement**
   - Cliquez sur "Create Web Service"
   - Render va automatiquement déployer votre application

7. **Vérifier le déploiement**
   - Attendez que le build et le déploiement soient terminés
   - Cliquez sur l'URL générée pour accéder à votre application

## Mise à jour du code

Lorsque vous effectuez des modifications et les poussez vers GitHub, Render redéploiera automatiquement votre application.

```bash
git add .
git commit -m "Description des modifications"
git push origin main
```

## Troubleshooting

Si vous rencontrez des problèmes lors du déploiement :

1. **Vérifiez les logs** - Render fournit des logs détaillés que vous pouvez consulter
2. **Problèmes CORS** - Assurez-vous que le Portail Orange autorise les requêtes depuis votre domaine Render
3. **Erreurs d'environnement** - Vérifiez que les variables d'environnement sont correctement configurées

Pour toute question ou problème, consultez la [documentation de Render](https://render.com/docs) ou contactez l'équipe de support.

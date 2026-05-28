# 🖥️ VM Monitoring Dashboard

> Dashboard de supervision en temps réel des machines virtuelles via SSH.

![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=flat-square&logo=fastapi&logoColor=white)
![Chart.js](https://img.shields.io/badge/Chart.js-4.x-FF6384?style=flat-square&logo=chartdotjs&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?style=flat-square&logo=docker&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)

---

## ✨ Fonctionnalités

| Fonctionnalité | Détail |
|---|---|
| 📊 Métriques temps réel | CPU, RAM et utilisation Disque par VM |
| 🔴🟢 Statut UP/DOWN | Disponibilité instantanée de chaque machine |
| 📈 Historique graphique | Courbes CPU/RAM sur les 60 derniers points |
| 💾 Analyse disque | Identification des répertoires les plus volumineux |
| ⚠️ Alertes automatiques | CPU ≥ 85% · RAM ≥ 90% · Disque ≥ 90% |
| 🔄 Rafraîchissement auto | Mise à jour toutes les 15 secondes |

---

## 🛠️ Stack technique

```
Backend      FastAPI + Paramiko (SSH)
Frontend     HTML / CSS / JavaScript + Chart.js
Container    Docker
```

---

## ✅ Prérequis

- **Docker** installé et opérationnel
- Accès **SSH** aux VMs cibles (port 22 ouvert)

---

## ⚙️ Configuration

### 1. Créer le fichier d'environnement

Copier l'exemple fourni et renseigner les valeurs :

```bash
cp .env.example .env
```

### 2. Renseigner le fichier `.env`

```env
# Identifiants SSH globaux
SSH_USERNAME=mon_login
SSH_PASSWORD=mon_mot_de_passe
SSH_PORT=22

# Déclaration des VMs (VM1_ à VM20_ supportées)
VM1_NAME=MonServeur1
VM1_HOST=192.168.1.10

VM2_NAME=MonServeur2
VM2_HOST=192.168.1.11
# Identifiants spécifiques (optionnel — écrase SSH_USERNAME/SSH_PASSWORD)
VM2_USER=root
VM2_PASS=mot_de_passe_specifique
```

> 💡 **Jusqu'à 20 VMs** peuvent être déclarées via les préfixes `VM1_` à `VM20_`.

---

## 🚀 Lancement

### Build & démarrage

```bash
docker build -t vm-monitor .

docker run -d \
  --name vm-monitor \
  --env-file .env \
  -p 8000:8000 \
  vm-monitor
```

### Accès au dashboard

```
http://localhost:8000
```

### Arrêt et suppression du conteneur

```bash
docker stop vm-monitor
docker rm vm-monitor
```

---

## 🔌 API Endpoints

| Méthode | Route | Description |
|---|---|---|
| `GET` | `/` | Dashboard web |
| `GET` | `/api/metrics` | Métriques de toutes les VMs |
| `GET` | `/api/history/{vm_host}` | Historique CPU/RAM d'une VM |
| `GET` | `/api/disk/{vm_host}` | Analyse disque d'une VM |
| `GET` | `/health` | Santé de l'API |

---

## 📁 Structure du projet

```
vm-monitor/
├── Dockerfile
├── .env.example
├── .env              # (non versionné)
├── main.py           # Application FastAPI
├── requirements.txt
└── templates/
    └── index.html    # Dashboard frontend
```

---

## 🔐 Sécurité

- Ne jamais versionner le fichier `.env` (ajoutez-le à votre `.gitignore`)
- Privilégier l'authentification par **clé SSH** plutôt que par mot de passe en production
- Restreindre l'accès au port `8000` via un reverse proxy ou un pare-feu si exposé au réseau

---

*Projet personnel — Supervision d'infrastructure interne.*

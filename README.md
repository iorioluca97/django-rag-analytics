# 📄 RAG-based Document Analytics & Summarization
Non avevo nulla da fare nel weekend e django non l'ho mai visto quindi beccati questo.. 

*Progetto Django per il caricamento, l’analisi e il riassunto di documenti (PDF, articoli, report) tramite Retrieval-Augmented Generation (RAG).*

---

## 🚀 Avvia in GitHub Codespaces

[![Apri in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://github.com/codespaces/new?hide_repo_select=true&repo=iorioluca97/django-rag-analytics&ref=dev)

### ⚙️ Setup iniziale
   
1. **Configura le variabili d'ambiente:**
   ```bash
   # Crea il file .env
   cp .env.example .env
   
   # Modifica con le tue chiavi
   nano .env
   ```

2. **Avvia l'applicazione:**
   ```bash
   # Con Docker
   docker-compose up --build
   
   # Oppure localmente
   python manage.py runserver
   ```

3. **Configura OpenAI API Key** tramite l'interfaccia web (opzionale se già configurata in .env)

4. **Carica un PDF e analizzalo!**

> 📋 **Nota**: MongoDB è configurato automaticamente tramite variabili d'ambiente. Vedi [ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md) per dettagli completi.


## ✨ Caratteristiche principali
* Upload di documenti PDF tramite interfaccia web

* Estrazione del testo dai documenti caricati, generazione della table of content

* Generazione di embeddings per ricerca semantica (integrazione con LangChain)

* Estrazione di immagini e insight

* Riassunti automatici personalizzabili

## 🧪 Uso
* Carica i documenti PDF tramite il form di upload:

![alt text](./readme_media/home.png)

* Utilizza le funzionalità di ricerca e sintesi nei documenti caricati (da implementare)

![alt text](./readme_media/document.png)

* Utilizza l'analisi documentale per estrarre maggiori informazioni, immagini, table of content e molto altro!

![alt text](./readme_media/analytics_1.png)

![alt text](./readme_media/analytics_2.png)

---
🗂️ Struttura del progetto

```
rag_project/
├── documents/            # App principale
│   ├── migrations/
│   ├── templates/
│   │   └── documents/
│   │       ├── home.html
│   │       └── document.html
│   │       └── analytics.html
│   ├── views.py
│   ├── models.py
│   └── urls.py
├── rag_project/          # Configurazione principale Django
├── templates/            # Cartella template globale
├── manage.py
└── requirements.txt
```

## 🔭 Prossimi sviluppi
* Integrazione con database vettoriale (es. MongoDB + Atlas Vector Search)

* Chat interattiva basata su RAG

* Estrazione di entità nominate (NER)

* Altro? Suggerisci pure!!

## 🤝 Contribuire
Vuoi contribuire? Sentiti libero di aprire una issue o inviare una pull request.

## 📄 Licenza
Distribuito sotto [Licenza MIT](LICENSE)

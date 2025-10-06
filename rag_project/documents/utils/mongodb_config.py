"""
MongoDB Configuration Helper
Gestisce le configurazioni SSL e le connessioni MongoDB
"""

import os
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from .logger import logger

def create_mongodb_client(uri: str, **kwargs):
    """
    Crea un client MongoDB con configurazioni SSL robuste
    
    Args:
        uri (str): MongoDB connection string
        **kwargs: Parametri aggiuntivi per MongoClient
    
    Returns:
        MongoClient: Client MongoDB configurato
    """
    
    # Configurazioni SSL di default
    ssl_configs = [
        # Configurazione 1: SSL con certificati invalidi permessi (per sviluppo)
        {
            "tlsAllowInvalidCertificates": True,
            "tlsAllowInvalidHostnames": True,
            "connectTimeoutMS": 10000,
            "serverSelectionTimeoutMS": 10000
        },
        # Configurazione 2: SSL standard
        {
            "connectTimeoutMS": 10000,
            "serverSelectionTimeoutMS": 10000
        },
        # Configurazione 3: Senza SSL (fallback)
        {
            "tls": False
        }
    ]
    
    for i, ssl_config in enumerate(ssl_configs):
        try:
            logger.debug(f"Trying MongoDB connection config {i + 1}")
            config = {
                "server_api": ServerApi("1"),
                **ssl_config,
                **kwargs
            }
            
            client = MongoClient(uri, **config)
            
            # Test della connessione
            client.admin.command("ping")
            logger.info(f"MongoDB connected successfully with config {i + 1}")
            return client
            
        except Exception as e:
            logger.warning(f"MongoDB config {i + 1} failed: {e}")
            continue
    
    # Se tutte le configurazioni falliscono
    raise Exception("All MongoDB connection configurations failed")

def test_mongodb_connection(uri: str) -> bool:
    """
    Testa la connessione MongoDB senza sollevare eccezioni
    
    Args:
        uri (str): MongoDB connection string
        
    Returns:
        bool: True se la connessione è riuscita, False altrimenti
    """
    try:
        client = create_mongodb_client(uri)
        client.close()
        return True
    except Exception as e:
        logger.error(f"MongoDB connection test failed: {e}")
        return False

def get_mongodb_status(uri: str) -> dict:
    """
    Restituisce lo stato della connessione MongoDB
    
    Args:
        uri (str): MongoDB connection string
        
    Returns:
        dict: Stato della connessione con dettagli
    """
    try:
        client = create_mongodb_client(uri)
        
        # Informazioni sul server
        server_info = client.server_info()
        
        # Lista dei database
        databases = client.list_database_names()
        
        client.close()
        
        return {
            "status": "connected",
            "version": server_info.get("version", "unknown"),
            "databases": databases,
            "error": None
        }
        
    except Exception as e:
        return {
            "status": "error",
            "version": None,
            "databases": [],
            "error": str(e)
        }

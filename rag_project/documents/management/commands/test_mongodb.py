"""
Django management command per testare la connessione MongoDB
"""

from django.core.management.base import BaseCommand
from django.conf import settings
import os
from documents.utils.mongodb_config import test_mongodb_connection, get_mongodb_status

class Command(BaseCommand):
    help = 'Testa la connessione MongoDB e mostra lo stato del database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--uri',
            type=str,
            help='MongoDB URI da testare (opzionale, usa MONGO_URI dal settings)',
        )

    def handle(self, *args, **options):
        # Ottieni l'URI MongoDB
        mongo_uri = options.get('uri') or os.getenv('MONGO_URI')
        
        if not mongo_uri:
            self.stdout.write(
                self.style.ERROR('❌ MONGO_URI non configurato. Impostalo nel file .env o usa --uri')
            )
            return

        self.stdout.write('🔍 Testando connessione MongoDB...')
        self.stdout.write(f'URI: {mongo_uri[:50]}...' if len(mongo_uri) > 50 else f'URI: {mongo_uri}')

        # Test connessione
        if test_mongodb_connection(mongo_uri):
            self.stdout.write(
                self.style.SUCCESS('✅ Connessione MongoDB riuscita!')
            )
            
            # Mostra dettagli del database
            status = get_mongodb_status(mongo_uri)
            if status['status'] == 'connected':
                self.stdout.write(f'📊 Versione MongoDB: {status["version"]}')
                self.stdout.write(f'🗄️  Database disponibili: {len(status["databases"])}')
                for db in status['databases'][:5]:  # Mostra solo i primi 5
                    self.stdout.write(f'   - {db}')
                if len(status['databases']) > 5:
                    self.stdout.write(f'   ... e altri {len(status["databases"]) - 5} database')
            else:
                self.stdout.write(
                    self.style.WARNING(f'⚠️  Connessione riuscita ma errore nel recupero info: {status["error"]}')
                )
        else:
            self.stdout.write(
                self.style.ERROR('❌ Connessione MongoDB fallita!')
            )
            self.stdout.write('💡 Suggerimenti:')
            self.stdout.write('   1. Verifica che l\'URI MongoDB sia corretto')
            self.stdout.write('   2. Controlla che il cluster sia attivo')
            self.stdout.write('   3. Verifica le credenziali e i permessi')
            self.stdout.write('   4. Controlla la configurazione di rete/firewall')

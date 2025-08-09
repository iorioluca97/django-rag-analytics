echo "---------------- Install dependencies ..."
# poetry install --no-root --only main

echo "---------------- Auth environment file ..."
chmod 644 /workspaces/django-rag-analytics/rag_project/.env

echo "---------------- Set WD ..."
cd ./rag_project
ls -ll

echo "---------------- Make migrations ..."
poetry run python manage.py makemigrations

echo "---------------- Run migrations..."
poetry run python manage.py migrate

echo "---------------- Start app..."
poetry run python manage.py runserver
#!/usr/bin/env bash
# exit on error
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Seed database with menu items and categories
python -m catering_app.seed_from_files

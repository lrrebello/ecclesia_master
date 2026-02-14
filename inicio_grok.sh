find . -type f \
    ! -path "*/node_modules/*" \
    ! -path "*/.git/*" \
    ! -path "*/venv/*" \
    ! -path "*/.idea/*" \
    ! -path "*/dist/*" \
    ! -path "*/build/*" \
    ! -path "*/static/uploads/*" \
    ! -path "*/__pycache__/*" \
    ! -path "*/migrations/versions/*" \
    \( -name "*.py" \
       -o -name "*.html" \
       -o -name "*.css" \
       -o -name "*.js" \
       -o -name "*.ts" \
       -o -name "*.json" \
       -o -name "*.md" \
       -o -name "*.yaml" \
       -o -name "*.yml" \
       -o -name "*.txt" \
       -o -name "*.sql" \
       -o -name "Dockerfile" \
       -o -name ".env*" \
       -o -name "requirements.txt" \
       -o -name "Pipfile*" \
       -o -name "Procfile" \
       -o -name "README*" \) \
    -print0 | sort -z | xargs -0 -I {} sh -c 'printf "\n\n===== %s =====\n" "{}"; cat "{}"; printf "\n"' > inicio_grok_completo.txt 2> erros.txt

# 1. Modelos principais
echo -e "\n===== app/core/models.py =====\n" > core-models.txt && cat app/core/models.py >> core-models.txt

# 2. Rotas de edificação
echo -e "\n===== app/modules/edification/routes.py =====\n" > edification-routes.txt && cat app/modules/edification/routes.py >> edification-routes.txt

# 3. Rotas de membros
echo -e "\n===== app/modules/members/routes.py =====\n" > members-routes.txt && cat app/modules/members/routes.py >> members-routes.txt

# 4. Rotas de auth (ajusta o caminho se for diferente)
echo -e "\n===== app/modules/auth/routes.py =====\n" > auth-routes.txt && cat app/modules/auth/routes.py >> auth-routes.txt 2>/dev/null || echo "Arquivo não encontrado"

# 5. Templates de edificação (exemplo com alguns principais)
echo -e "\n===== gallery.html =====\n" > templates-edification.txt && cat app/templates/edification/gallery.html >> templates-edification.txt
echo -e "\n===== add_media.html =====\n" >> templates-edification.txt && cat app/templates/edification/add_media.html >> templates-edification.txt
echo -e "\n===== gallery_album.html =====\n" >> templates-edification.txt && cat app/templates/edification/gallery_album.html >> templates-edification.txt

# 6. Templates de members (dashboard + outros)
echo -e "\n===== dashboard.html =====\n" > templates-members.txt && cat app/templates/members/dashboard.html >> templates-members.txt

# 7. Utils (Gemini + extrator)
echo -e "\n===== gemini_service.py =====\n" > utils-and-services.txt && cat app/utils/gemini_service.py >> utils-and-services.txt
echo -e "\n===== text_extractor.py =====\n" >> utils-and-services.txt && cat app/utils/text_extractor.py >> utils-and-services.txt

# 8. CSS principal (ajusta o caminho/nome se for diferente)
echo -e "\n===== main.css ou style.css =====\n" > static-css-main.txt && cat app/static/css/main.css >> static-css-main.txt 2>/dev/null || echo "Ajuste o caminho"

# 9. Configurações gerais
echo -e "\n===== config.py =====\n" > config-and-init.txt && cat config.py >> config-and-init.txt 2>/dev/null
echo -e "\n===== __init__.py =====\n" >> config-and-init.txt && cat app/__init__.py >> config-and-init.txt
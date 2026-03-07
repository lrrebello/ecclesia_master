# app/utils/logger.py
from app.core.models import db, SystemLog
from flask_login import current_user
from flask import request
import json
from datetime import datetime

def log_action(action, module, description, old_values=None, new_values=None, church_id=None):
    """Função para registrar ações no sistema."""
    try:
        # Pegar o ID do usuário atual (se estiver logado)
        user_id = None
        if current_user and not current_user.is_anonymous:
            user_id = current_user.id
        
        # Se não passou church_id, tenta pegar do usuário atual
        if not church_id and current_user and not current_user.is_anonymous:
            church_id = current_user.church_id
        
        log_entry = SystemLog(
            user_id=user_id,
            church_id=church_id,
            action=action,
            module=module,
            description=description,
            old_values=old_values,
            new_values=new_values,
            ip_address=request.remote_addr if request else None,
            created_at=datetime.utcnow()
        )
        
        db.session.add(log_entry)
        db.session.commit()
        
    except Exception as e:
        # Não deve impedir a ação principal, apenas loga o erro
        print(f"Erro ao registrar log: {e}")
        db.session.rollback()
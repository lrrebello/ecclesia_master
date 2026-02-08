from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.core.models import Study, Devotional, KidsActivity, StudyQuestion, db
import markdown
import json

edification_bp = Blueprint('edification', __name__)

@edification_bp.route('/studies')
@login_required
def list_studies():
    studies = Study.query.order_by(Study.created_at.desc()).all()
    return render_template('edification/studies.html', studies=studies)

@edification_bp.route('/study/<int:id>')
@login_required
def view_study(id):
    study = Study.query.get_or_404(id)
    content_html = markdown.markdown(study.content)
    return render_template('edification/view_study.html', study=study, content_html=content_html)

@edification_bp.route('/kids')
@login_required
def kids_corner():
    activities = KidsActivity.query.order_by(KidsActivity.created_at.desc()).all()
    return render_template('edification/kids.html', activities=activities)

@edification_bp.route('/admin/add_kids_activity', methods=['GET', 'POST'])
@login_required
def add_kids_activity():
    if current_user.role not in ['admin', 'pastor_leader', 'ministry_leader']:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('edification.kids_corner'))
        
    if request.method == 'POST':
        new_act = KidsActivity(
            title=request.form.get('title'),
            content=request.form.get('content'),
            age_group=request.form.get('age_group')
        )
        db.session.add(new_act)
        db.session.commit()
        flash('Atividade infantil publicada!', 'success')
        return redirect(url_for('edification.kids_corner'))
    return render_template('edification/add_kids.html')

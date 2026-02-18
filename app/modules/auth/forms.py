# app/modules/auth/forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError
from app.core.models import User
from flask import current_app

class RegistrationForm(FlaskForm):
    name = StringField('Nome completo', 
                       validators=[DataRequired(message="O nome é obrigatório"),
                                   Length(min=3, max=100, message="Nome deve ter entre 3 e 100 caracteres")])

    email = StringField('E-mail', 
                        validators=[DataRequired(message="O e-mail é obrigatório"),
                                    Email(message="Digite um e-mail válido")])

    password = PasswordField('Senha', 
                             validators=[DataRequired(message="A senha é obrigatória"),
                                         Length(min=6, message="A senha deve ter pelo menos 6 caracteres")])

    password2 = PasswordField('Confirmar senha', 
                              validators=[DataRequired(message="Confirme a senha"),
                                          EqualTo('password', message="As senhas não conferem")])

    data_consent = BooleanField('Eu concordo com a coleta e tratamento dos meus dados pessoais (LGPD/RGPD)',
                                validators=[DataRequired(message="Você precisa concordar com o uso dos dados")])

    submit = SubmitField('Criar conta')

    def validate_email(self, email):
        """Verifica se o e-mail já existe no banco"""
        user = User.query.filter_by(email=email.data.lower().strip()).first()
        if user:
            raise ValidationError('Este e-mail já está cadastrado. Faça login ou use outro e-mail.')
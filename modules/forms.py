from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, IntegerField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, NumberRange, Regexp
from modules.database import authenticate_user, get_user_by_id
import re

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=20)])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired(), 
        Length(min=4, max=20, message='Username must be between 4 and 20 characters')
    ])
    email = StringField('Email', validators=[
        DataRequired(), 
        Email(message='Please enter a valid email address')
    ])
    password = PasswordField('Password', validators=[
        DataRequired(), 
        Length(min=6, message='Password must be at least 6 characters long')
    ])
    password2 = PasswordField('Repeat Password', validators=[
        DataRequired(), 
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Register')

class User:
    """User class for Flask-Login"""
    def __init__(self, user_data):
        self.id = user_data['id']
        self.username = user_data['username']
        self.email = user_data['email']
        self.is_authenticated = True
        self.is_active = True
        self.is_anonymous = False
    
    def get_id(self):
        return str(self.id)
    
    @staticmethod
    def get(user_id):
        user_data = get_user_by_id(user_id)
        if user_data:
            return User(user_data)
        return None

class EcommerceScrapingForm(FlaskForm):
    """Form untuk konfigurasi scraping E-Commerce (Tokopedia/Shopee)"""
    
    def validate_keyword(self, field):
        """Custom validator untuk keyword"""
        keyword = field.data.strip()
        
        # Cek panjang minimum
        if len(keyword) < 2:
            raise ValidationError('Keyword harus minimal 2 karakter')
        
        # Cek karakter berbahaya
        dangerous_chars = ['<', '>', '"', "'", '&', ';', '|', '`', '\\', '/']
        if any(char in keyword for char in dangerous_chars):
            raise ValidationError('Keyword mengandung karakter yang tidak diizinkan')
        
        # Cek apakah hanya spasi
        if not keyword or keyword.isspace():
            raise ValidationError('Keyword tidak boleh kosong atau hanya berisi spasi')
    
    def validate_max_products(self, field):
        """Custom validator untuk jumlah maksimal produk"""
        if field.data < 50:
            raise ValidationError('Jumlah produk harus minimal 50')
        if field.data > 1000:
            raise ValidationError('Jumlah produk maksimal adalah 1000')
    
    platform = SelectField(
        'Platform E-Commerce',
        choices=[
            ('tokopedia', 'Tokopedia'),
            ('shopee', 'Shopee')
        ],
        default='tokopedia',
        validators=[DataRequired(message='Platform wajib dipilih')],
        render_kw={'class': 'form-select'}
    )
    
    keyword = StringField(
        'Keyword Pencarian Produk',
        validators=[
            DataRequired(message='Keyword wajib diisi'),
            Length(min=2, max=100, message='Keyword harus antara 2-100 karakter')
        ],
        render_kw={
            'placeholder': 'Contoh: laptop, baju, skincare, smartphone',
            'class': 'form-control'
        }
    )
    
    max_products = IntegerField(
        'Jumlah Produk',
        validators=[
            DataRequired(message='Jumlah produk wajib diisi'),
            NumberRange(min=50, max=1000, message='Jumlah produk harus antara 50-1000')
        ],
        default=50,
        render_kw={
            'class': 'form-control',
            'type': 'number',
            'min': '50',
            'max': '1000',
            'step': '10'
        }
    )
    
    submit = SubmitField(
        'Mulai Scraping',
        render_kw={'class': 'btn btn-primary btn-lg w-100'}
    )

# Alias untuk backward compatibility
TokopediaScrapingForm = EcommerceScrapingForm

class ScrapingHistoryForm(FlaskForm):
    """Form untuk filter history scraping"""
    
    date_from = StringField(
        'Dari Tanggal',
        render_kw={
            'type': 'date',
            'class': 'form-control'
        }
    )
    
    date_to = StringField(
        'Sampai Tanggal',
        render_kw={
            'type': 'date',
            'class': 'form-control'
        }
    )
    
    keyword_filter = StringField(
        'Filter Keyword',
        render_kw={
            'placeholder': 'Cari berdasarkan keyword...',
            'class': 'form-control'
        }
    )
    
    submit = SubmitField(
        'Filter',
        render_kw={'class': 'btn btn-secondary'}
    )
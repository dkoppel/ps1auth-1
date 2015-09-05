from django.contrib.sites.shortcuts import get_current_site
from django.template import loader
from django import forms
from django.forms.widgets import HiddenInput
from django.contrib.auth import get_user_model
from django.conf import settings
from accounts.models import PS1User
from ldap3.core.exceptions import LDAPConstraintViolationResult
from pprint import pprint
#from .tokens import default_token_generator
from .backends import PS1Backend
from .models import PS1Group
from .tokens import *


class PasswordResetForm(forms.Form):
    """
    Form grabbed from https://github.com/django/django/blob/6118d6d1c982e428cf398ac998eb9f0baba15bad/django/contrib/auth/forms.py#L210-L250
    """
    email = forms.EmailField(label=("Email"), max_length=254)

    def save(self, domain_override=None,
             subject_template_name='registration/password_reset_subject.txt',
             email_template_name='registration/password_reset_email.html',
             use_https=False, token_generator=default_token_generator,
             from_email=None, request=None, html_email_template_name=None):
        """
        Generates a one-use only link for resetting password and sends to the
        user.
        """
        from django.core.mail import send_mail
        UserModel = get_user_model()
        email_address = self.cleaned_data["email"]
        users = PS1User.objects.get_users_by_field("mail", email_address)
        for user in users:
            # Make sure that no email is sent to a user that actually has
            # a password marked as unusable

            #HEFTODO implement has_unusable_password
            #if not user.has_usable_password():
            #    continue
            if not domain_override:
                current_site = get_current_site(request)
                site_name = current_site.name
                domain = current_site.domain
            else:
                site_name = domain = domain_override
            # ignore the token_generator that was passed in
            token = default_token_generator.make_token(user)
            c = {
                'email': email_address,
                'domain': domain,
                'site_name': site_name,
                'uid': user.object_guid,
                'user': user,
                'token': token,
                'protocol': 'https' if use_https else 'http',
            }
            if not from_email:
                from_email = settings.SERVER_EMAIL
            subject = loader.render_to_string(subject_template_name, c)
            # Email subject *must not* contain newlines
            subject = ''.join(subject.splitlines())
            email_body = loader.render_to_string(email_template_name, c)
            user_email = user.ldap_user['mail'][0]
            send_mail(subject, email_body, from_email, [user_email])

class SetPasswordForm(forms.Form):
    """
    A form that lets a user change set his/her password without entering the
    old password
    ripped from https://github.com/django/django/blob/6118d6d1c982e428cf398ac998eb9f0baba15bad/django/contrib/auth/forms.py#L253-L285
    """
    error_messages = {
        'password_mismatch': "The two password fields didn't match.",
    }
    new_password1 = forms.CharField(label="New password",
                                    widget=forms.PasswordInput)
    new_password2 = forms.CharField(label="New password confirmation",
                                    widget=forms.PasswordInput)

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super(SetPasswordForm, self).__init__(*args, **kwargs)

    def clean_new_password2(self):
        password1 = self.cleaned_data.get('new_password1')
        password2 = self.cleaned_data.get('new_password2')
        if password1 and password2:
            if password1 != password2:
                raise forms.ValidationError(
                    self.error_messages['password_mismatch'],
                    code='password_mismatch',
                )
        return password2

    def clean(self):
        """
        Warning, this function does the actual password resetting.
        """
        try:
            password = self.cleaned_data.get('new_password1') or ""
            self.user.set_password(password)
        except LDAPConstraintViolationResult as e:
            raise forms.ValidationError(e.message)
        return self.cleaned_data

    def save(self, commit=True):
        """
        Warning, this function does not do work, the actual work is done in clean()
        """
        return self.user

class EditUserGroupForm(forms.Form):
    ACTIONS = (
        ('add',''),
        ('remove','')
    )
    account_pk = forms.CharField(widget=HiddenInput())
    group_dn = forms.CharField(widget=HiddenInput())
    action = forms.ChoiceField(widget=HiddenInput, choices=ACTIONS)
    _user = None
    _group = None

    def apply(self):
        if(self.cleaned_data['action'] == 'add'):
            return self.group.add_user(self.account)
        elif(self.cleaned_data['action'] == 'remove'):
            return self.group.remove_user(self.account)
        else:
            return False

    @property
    def group(self):
        if not self._group:
            self._group = PS1Group.objects.get(dn=self.cleaned_data['group_dn'])
        return self._group


    @property
    def account(self):
        if not self._user:
            self._account = PS1User.objects.get(pk=self.cleaned_data['account_pk'])
        return self._account

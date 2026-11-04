import re
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Task, SubTask, Category, Reminder
from django.utils import timezone


class TaskForm(forms.ModelForm):
    reminder_at = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(
            attrs={
                'type': 'datetime-local',
                'class': 'form-input'
            }
        )
    )
    tags_input = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                'placeholder': 'Enter tags separated by commas',
                'class': 'form-input'
            }
        ),
        label='Tags'
    )

    class Meta:
        model = Task
        fields = [
            'title', 'description', 'priority', 'status', 
            'category', 'due_date', 'reminder_at', 
            'is_pinned', 'is_recurring', 'recurrence_interval'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Task title'}),
            'description': forms.Textarea(attrs={'class': 'form-textarea', 'placeholder': 'Add details...', 'rows': 4}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'due_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-input'}),
            'is_pinned': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'is_recurring': forms.CheckboxInput(attrs={'class': 'form-checkbox', 'id': 'id_is_recurring'}),
            'recurrence_interval': forms.Select(attrs={'class': 'form-select', 'id': 'id_recurrence_interval'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user:
            self.fields['category'].queryset = Category.objects.filter(user=user)

        # Pre-populate tags if editing
        if self.instance.pk and self.instance.tags:
            self.fields['tags_input'].initial = ', '.join(self.instance.tags)

    def clean_category(self):
        category = self.cleaned_data.get('category')
        if category and self.user and category.user != self.user:
            raise forms.ValidationError("You do not have permission to select this category.")
        return category

    def clean_tags_input(self):
        tags_str = self.cleaned_data.get('tags_input', '')
        if tags_str:
            cleaned_tags = []
            for tag in tags_str.split(','):
                t = tag.strip()[:50]
                if t and t not in cleaned_tags:
                    cleaned_tags.append(t)
            return cleaned_tags[:20]
        return []

    def clean_reminder_at(self):
        reminder = self.cleaned_data.get('reminder_at')
        due = self.cleaned_data.get('due_date')
        if reminder and due and reminder > due:
            raise forms.ValidationError("Reminder must be before the due date.")
        if reminder and reminder < timezone.now():
            raise forms.ValidationError("Reminder cannot be in the past.")
        return reminder

    def clean(self):
        cleaned_data = super().clean()
        is_recurring = cleaned_data.get('is_recurring')
        interval = cleaned_data.get('recurrence_interval')
        if is_recurring and not interval:
            self.add_error('recurrence_interval', 'Please select a recurrence interval for recurring tasks.')
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.tags = self.cleaned_data.get('tags_input', [])
        if commit:
            instance.save()
        return instance


class SubTaskForm(forms.ModelForm):
    class Meta:
        model = SubTask
        fields = ['title']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Subtask title'}),
        }

    def clean_title(self):
        title = self.cleaned_data.get('title', '').strip()
        if not title:
            raise forms.ValidationError("Subtask title cannot be empty.")
        return title[:200]


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'color', 'icon']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Category name'}),
            'color': forms.TextInput(attrs={'type': 'color', 'class': 'form-color'}),
            'icon': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'fa-icon-name'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise forms.ValidationError("Category name cannot be empty.")
        return name[:50]

    def clean_color(self):
        color = self.cleaned_data.get('color', '#8b5cf6').strip()
        if not re.match(r'^#[0-9a-fA-F]{6}$', color):
            raise forms.ValidationError("Enter a valid hex color code (e.g. #8b5cf6).")
        return color

    def clean_icon(self):
        icon = self.cleaned_data.get('icon', 'fa-tag').strip()
        if not re.match(r'^[a-zA-Z0-9_-]+$', icon):
            raise forms.ValidationError("Icon can only contain letters, numbers, hyphens, and underscores.")
        return icon[:30]


class ReminderForm(forms.ModelForm):
    class Meta:
        model = Reminder
        fields = ['remind_at']
        widgets = {
            'remind_at': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-input'}),
        }


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'Email'}))

    class Meta:
        model = User
        fields = ('username', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-input', 'placeholder': 'Username'})
        if 'password1' in self.fields:
            self.fields['password1'].widget.attrs.update({'class': 'form-input', 'placeholder': 'Password'})
        if 'password2' in self.fields:
            self.fields['password2'].widget.attrs.update({'class': 'form-input', 'placeholder': 'Confirm Password'})

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email address already exists.")
        return email

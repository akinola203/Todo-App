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
        if user:
            self.fields['category'].queryset = Category.objects.filter(user=user)

        # Pre-populate tags if editing
        if self.instance.pk and self.instance.tags:
            self.fields['tags_input'].initial = ', '.join(self.instance.tags)

    def clean_tags_input(self):
        tags_str = self.cleaned_data.get('tags_input', '')
        if tags_str:
            return [tag.strip() for tag in tags_str.split(',') if tag.strip()]
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


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'color', 'icon']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Category name'}),
            'color': forms.TextInput(attrs={'type': 'color', 'class': 'form-color'}),
            'icon': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'fa-icon-name'}),
        }


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

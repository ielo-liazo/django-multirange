from django import forms


class MultiRangeFormField(forms.Field):
    """Form field corresponding to `MultiRangeField`.

    Implement widget handling and validation here.
    """

    def to_python(self, value):
        return value

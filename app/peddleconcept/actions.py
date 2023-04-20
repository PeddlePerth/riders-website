import csv
from collections import OrderedDict
from functools import wraps, singledispatch

from django.core.exceptions import FieldDoesNotExist
from django.http import HttpResponse
from django.contrib import messages

# Export CSV function used with gratitude from https://djangosnippets.org/snippets/2995/
def prep_field(obj, field):
    """
    (for download_as_csv action)
    Returns the field as a (unicode) string. If the field is a callable, it
    attempts to call it first, without arguments.
    """

    if '__' in field:
        bits = field.split('__')
        field = bits.pop()

        for bit in bits:
            obj = getattr(obj, bit, None)

            if obj is None:
                return ""

    attr = getattr(obj, field)
    output = attr() if callable(attr) else attr
    return str(output) if output is not None else ""


@singledispatch
def download_as_csv(modeladmin, request, queryset):
    """
    Generic csv export admin action.

    Example:

        class ExampleModelAdmin(admin.ModelAdmin):
            raw_id_fields = ('field1',)
            list_display = ('field1', 'field2', 'field3',)
            actions = [download_as_csv,]
            download_as_csv_fields = [
                'field1',
                ('foreign_key1__foreign_key2__name', 'label2'),
                ('field3', 'label3'),
            ],
            download_as_csv_header = True
    """
    fields = getattr(modeladmin, 'download_as_csv_fields', None)
    exclude = getattr(modeladmin, 'download_as_csv_exclude', None)
    header = getattr(modeladmin, 'download_as_csv_header', True)
    verbose_names = getattr(modeladmin, 'download_as_csv_verbose_names', True)

    opts = modeladmin.model._meta

    def fname(field):
        if verbose_names:
            return str(field.verbose_name).capitalize()
        else:
            return field.name

    # field_names is a map of {field lookup path: field label}
    if exclude:
        field_names = OrderedDict(
            (f.name, fname(f)) for f in opts.fields if f not in exclude
        )
    elif fields:
        field_names = OrderedDict()
        for spec in fields:
            if isinstance(spec, (list, tuple)):
                field_names[spec[0]] = spec[1]
            else:
                try:
                    f = opts.get_field(spec)
                except FieldDoesNotExist:
                    field_names[spec] = spec
                else:
                    field_names[spec] = fname(f)
    else:
        field_names = OrderedDict(
            (f.name, fname(f)) for f in opts.fields
        )

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename=%s.csv' % (
            str(opts).replace('.', '_')
        )

    writer = csv.writer(response)

    if header:
        writer.writerow(field_names.values())

    for obj in queryset:
        writer.writerow([prep_field(obj, field) for field in field_names.keys()])
    return response

download_as_csv.short_description = "Download selected objects as CSV file"


@download_as_csv.register(str)
def _(description):
    """
    (overridden dispatcher)
    Factory function for making a action with custom description.

    Example:

        class ExampleModelAdmin(admin.ModelAdmin):
            raw_id_fields = ('field1',)
            list_display = ('field1', 'field2', 'field3',)
            actions = [download_as_csv("Export Special Report"),]
            download_as_csv_fields = [
                'field1',
                ('foreign_key1__foreign_key2__name', 'label2'),
                ('field3', 'label3'),
            ],
            download_as_csv_header = True
    """
    @wraps(download_as_csv)
    def wrapped_action(modeladmin, request, queryset):
        return download_as_csv(modeladmin, request, queryset)
    wrapped_action.short_description = description
    return wrapped_action

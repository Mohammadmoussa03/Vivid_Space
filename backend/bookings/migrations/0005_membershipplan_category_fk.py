"""Convert MembershipPlan.category from a fixed CharField enum to a FK to the
new PackageCategory model, preserving existing assignments.

Done as add-tmp-FK → copy data → drop old field → rename, so it needs no
interactive rename prompt and loses no data.
"""
from django.db import migrations, models
import django.db.models.deletion

# Display names for the original enum slugs; anything else is title-cased.
KNOWN = {
    'private_office': 'Private Office',
    'dedicated_desk': 'Dedicated Desk',
    'virtual_office': 'Virtual Office',
    'membership': 'Membership',
    'custom': 'Customized Package',
}


def forwards(apps, schema_editor):
    MembershipPlan = apps.get_model('bookings', 'MembershipPlan')
    PackageCategory = apps.get_model('bookings', 'PackageCategory')

    for order, plan in enumerate(MembershipPlan.objects.all()):
        slug = (plan.category or 'membership').strip() or 'membership'
        name = KNOWN.get(slug, slug.replace('_', ' ').replace('-', ' ').title())
        category, created = PackageCategory.objects.get_or_create(
            slug=slug, defaults={'name': name, 'order': order},
        )
        plan.category_tmp = category
        plan.save(update_fields=['category_tmp'])


def backwards(apps, schema_editor):
    MembershipPlan = apps.get_model('bookings', 'MembershipPlan')
    for plan in MembershipPlan.objects.all():
        plan.category = plan.category_tmp.slug if plan.category_tmp else 'membership'
        plan.save(update_fields=['category'])


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0004_faq_galleryimage_packagecategory_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='membershipplan',
            name='category_tmp',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='plans', to='bookings.packagecategory',
            ),
        ),
        migrations.RunPython(forwards, backwards),
        migrations.RemoveField(model_name='membershipplan', name='category'),
        migrations.RenameField(
            model_name='membershipplan', old_name='category_tmp', new_name='category',
        ),
    ]

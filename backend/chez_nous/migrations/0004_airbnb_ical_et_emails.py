import secrets

from django.db import migrations, models

import chez_nous.models


def remplir_jetons(apps, schema_editor):
    Logement = apps.get_model("chez_nous", "Logement")
    for logement in Logement.objects.all():
        if logement.jeton_ical:
            continue
        logement.jeton_ical = secrets.token_urlsafe(32)
        logement.save(update_fields=["jeton_ical"])


class Migration(migrations.Migration):

    dependencies = [
        ("chez_nous", "0003_reservation_annulee_et_nuits"),
    ]

    operations = [
        migrations.AddField(
            model_name="logement",
            name="jeton_ical",
            field=models.CharField(max_length=64, null=True),
        ),
        migrations.RunPython(remplir_jetons, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="logement",
            name="jeton_ical",
            field=models.CharField(
                default=chez_nous.models.generer_jeton_ical,
                editable=False,
                max_length=64,
                unique=True,
                verbose_name="jeton du calendrier",
            ),
        ),
        migrations.AddField(
            model_name="logement",
            name="annonce_airbnb",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Nom ou identifiant de l’annonce, tel qu’il apparaît dans les e-mails Airbnb.",
                max_length=160,
                verbose_name="annonce Airbnb",
            ),
        ),
        migrations.AddField(
            model_name="logement",
            name="synchro_le",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="dernière synchronisation",
            ),
        ),
        migrations.AddField(
            model_name="logement",
            name="synchro_resultat",
            field=models.JSONField(
                blank=True,
                default=dict,
                verbose_name="résultat de synchronisation",
            ),
        ),
        migrations.AddField(
            model_name="logement",
            name="url_ical_airbnb",
            field=models.URLField(
                blank=True,
                default="",
                max_length=500,
                verbose_name="adresse iCal Airbnb",
            ),
        ),
        migrations.AddField(
            model_name="reservation",
            name="blocage",
            field=models.BooleanField(
                default=False,
                help_text="Dates bloquées sur Airbnb, sans client ni montant à recevoir.",
                verbose_name="blocage",
            ),
        ),
        migrations.AddField(
            model_name="reservation",
            name="code_airbnb",
            field=models.CharField(
                blank=True,
                default="",
                max_length=20,
                verbose_name="code de confirmation",
            ),
        ),
        migrations.AddField(
            model_name="reservation",
            name="nombre_voyageurs",
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                verbose_name="nombre de voyageurs",
            ),
        ),
        migrations.AddField(
            model_name="reservation",
            name="uid_ical",
            field=models.CharField(
                blank=True,
                default="",
                max_length=255,
                verbose_name="identifiant iCal",
            ),
        ),
        migrations.CreateModel(
            name="LectureEmails",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "le",
                    models.DateTimeField(blank=True, null=True, verbose_name="lue le"),
                ),
                (
                    "resultat",
                    models.JSONField(blank=True, default=dict, verbose_name="résultat"),
                ),
            ],
            options={
                "verbose_name": "lecture des e-mails",
                "verbose_name_plural": "lectures des e-mails",
            },
        ),
        migrations.CreateModel(
            name="MessageEmailTraite",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "message_id",
                    models.CharField(
                        max_length=500,
                        unique=True,
                        verbose_name="identifiant du message",
                    ),
                ),
                (
                    "traite_le",
                    models.DateTimeField(auto_now_add=True, verbose_name="traité le"),
                ),
            ],
            options={
                "verbose_name": "message traité",
                "verbose_name_plural": "messages traités",
                "ordering": ["-traite_le", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="reservation",
            constraint=models.UniqueConstraint(
                condition=~models.Q(uid_ical=""),
                fields=("logement", "uid_ical"),
                name="uid_ical_unique_par_logement",
            ),
        ),
        migrations.AddConstraint(
            model_name="reservation",
            constraint=models.UniqueConstraint(
                condition=~models.Q(code_airbnb=""),
                fields=("code_airbnb",),
                name="code_airbnb_unique",
            ),
        ),
    ]

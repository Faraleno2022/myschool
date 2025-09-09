from django.contrib import admin
from .models import DemandeInscriptionEcole, ConfigurationEcole, TemplateDocument, ClasseInscription, EcheancierInscription


@admin.register(DemandeInscriptionEcole)
class DemandeInscriptionEcoleAdmin(admin.ModelAdmin):
    list_display = ['nom_ecole', 'nom_demandeur', 'ville', 'statut', 'date_demande']
    list_filter = ['statut', 'type_ecole', 'ville', 'prefecture', 'date_demande']
    search_fields = ['nom_ecole', 'nom_demandeur', 'email_demandeur', 'ville']
    readonly_fields = ['date_demande', 'date_traitement']
    
    fieldsets = (
        ('Informations du demandeur', {
            'fields': ('nom_demandeur', 'prenom_demandeur', 'fonction_demandeur', 
                      'email_demandeur', 'telephone_demandeur')
        }),
        ('Informations de l\'école', {
            'fields': ('nom_ecole', 'nom_complet_ecole', 'type_ecole', 'adresse_ecole', 
                      'ville', 'prefecture', 'telephone_ecole', 'email_ecole', 'site_web')
        }),
        ('Direction', {
            'fields': ('nom_directeur', 'telephone_directeur')
        }),
        ('Documents légaux', {
            'fields': ('numero_autorisation', 'date_autorisation', 'logo_ecole', 
                      'document_autorisation', 'autres_documents')
        }),
        ('Statistiques', {
            'fields': ('nombre_eleves_estime', 'nombre_enseignants', 'niveaux_enseignes')
        }),
        ('Gestion de la demande', {
            'fields': ('statut', 'date_demande', 'date_traitement', 'traite_par', 
                      'notes_admin', 'motif_rejet', 'ecole_creee')
        }),
    )


@admin.register(ConfigurationEcole)
class ConfigurationEcoleAdmin(admin.ModelAdmin):
    list_display = ['ecole', 'afficher_logo_documents', 'prefixe_recu', 'prefixe_facture']
    list_filter = ['afficher_logo_documents', 'email_notifications', 'sms_notifications']
    search_fields = ['ecole__nom']


@admin.register(TemplateDocument)
class TemplateDocumentAdmin(admin.ModelAdmin):
    list_display = ['nom', 'type_document', 'ecole', 'est_actif', 'est_par_defaut']
    list_filter = ['type_document', 'est_actif', 'est_par_defaut']
    search_fields = ['nom', 'ecole__nom']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('nom', 'type_document', 'ecole', 'est_actif', 'est_par_defaut')
        }),
        ('Contenu du template', {
            'fields': ('contenu_html', 'styles_css')
        }),
    )


class ClasseInscriptionInline(admin.TabularInline):
    model = ClasseInscription
    extra = 1
    fields = ['nom', 'niveau', 'code_matricule', 'capacite_max', 'frais_inscription', 'tranche_1', 'tranche_2', 'tranche_3']


class EcheancierInscriptionInline(admin.StackedInline):
    model = EcheancierInscription
    extra = 0
    fields = ['annee_scolaire', 'date_echeance_inscription', 'date_echeance_tranche_1', 'date_echeance_tranche_2', 'date_echeance_tranche_3', 'autoriser_paiement_partiel', 'penalite_retard']


@admin.register(ClasseInscription)
class ClasseInscriptionAdmin(admin.ModelAdmin):
    list_display = ['nom', 'niveau', 'demande_inscription', 'capacite_max', 'total_annuel']
    list_filter = ['niveau', 'demande_inscription__statut']
    search_fields = ['nom', 'demande_inscription__nom_ecole']
    
    def total_annuel(self, obj):
        return f"{obj.total_annuel:,} GNF"
    total_annuel.short_description = "Total annuel"


@admin.register(EcheancierInscription)
class EcheancierInscriptionAdmin(admin.ModelAdmin):
    list_display = ['demande_inscription', 'annee_scolaire', 'date_echeance_inscription', 'penalite_retard']
    list_filter = ['annee_scolaire', 'autoriser_paiement_partiel']
    search_fields = ['demande_inscription__nom_ecole']

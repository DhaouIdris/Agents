# Demandes internes — guide Passerelle

Document entièrement synthétique. Version 1 publiée le 1er avril 2026.

## Préparer une demande

Une demande d'équipement contient un objet, une justification et le type d'équipement souhaité.
Préparer une demande crée un brouillon ; cela ne la soumet pas.
Avant la soumission, l'utilisateur doit voir le récapitulatif et confirmer explicitement.

## États possibles

BROUILLON : la demande est préparée mais non soumise.
SOUMISE : la demande a été enregistrée pour examen.
EN_COURS : le service compétent traite la demande.
TERMINEE : le traitement de la demande est terminé.
REJETEE : la demande n'a pas été acceptée ; un motif est disponible.

## Consultation

Le statut courant doit être consulté dans l'outil de suivi à partir de l'identifiant de demande.
Ce guide explique les états ; il ne contient aucun statut individuel à jour.
La consultation d'une demande est limitée aux personnes autorisées pour cette demande.

## Erreur de soumission

Après une interruption, l'application doit vérifier le résultat avant de soumettre à nouveau.
La même opération doit conserver son identifiant d'idempotence pour éviter un doublon.

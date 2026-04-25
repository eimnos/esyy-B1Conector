# Looker Studio ACL - Procedura Operativa

## Obiettivo

Limitare i dati visibili in Looker Studio in base a:

- email utente loggato
- codice cliente `ov_codice_cliente`

Mappatura gestita in BigQuery con tabella ACL:

- `vtronik-sap-reporting-cliente.sap_reporting.acl_utenti_clienti`

## Passi

1. Esegui lo script [looker_acl_setup.sql](C:/Progetti clienti/Vtronik/BI/sql/looker_acl_setup.sql) in BigQuery.
2. Popola la tabella ACL con email reali dei destinatari.
3. In Looker Studio crea (o modifica) la data source BigQuery usando una **Custom Query**.

### Dove incollare la query in Looker Studio

Percorso consigliato (nuova origine dati):

1. Apri `lookerstudio.google.com` e apri il report in modalita modifica.
2. Menu `Risorsa` -> `Gestisci origini dati aggiunte` -> `Aggiungi un'origine dati`.
3. Scegli connettore `BigQuery`.
4. Nella schermata di connessione, passa alla modalita `Query personalizzata` (`Custom Query`).
5. Incolla la query qui sotto e conferma con `Connetti` / `Aggiungi`.

Percorso alternativo (origine dati gia esistente):

1. `Risorsa` -> `Gestisci origini dati aggiunte`.
2. `Modifica` sull'origine BigQuery.
3. `Modifica connessione`.
4. Abilita `Query personalizzata` e incolla la query.

Query da incollare:

```sql
SELECT
  d.*
FROM `vtronik-sap-reporting-cliente.sap_reporting.stato_ordini_cliente` AS d
WHERE EXISTS (
  SELECT 1
  FROM `vtronik-sap-reporting-cliente.sap_reporting.acl_utenti_clienti` AS a
  WHERE a.is_active = TRUE
    AND LOWER(a.user_email) = LOWER(@DS_USER_EMAIL)
    AND (
      UPPER(TRIM(a.ov_codice_cliente)) = '__ALL__'
      OR a.ov_codice_cliente = d.ov_codice_cliente
    )
)
```

Importante:

- `@DS_USER_EMAIL` funziona solo dentro Looker Studio (Custom Query del data source).
- Se esegui la stessa query nella console BigQuery, il parametro non esiste e la query fallisce.

4. Condividi il report solo come Viewer (non Editor).
5. Verifica con due account diversi che ciascuno veda solo i propri record.

## Note importanti

- Se un utente non ha mapping ACL attivo, vede report vuoto.
- Normalizza sempre le email in minuscolo lato ACL (`LOWER`).
- Se un utente deve vedere piu codici cliente, inserisci piu righe ACL con la stessa email.
- Se vuoi un master user che veda tutto, inserisci una riga ACL con:
  - `user_email = email utente master`
  - `ov_codice_cliente = '__ALL__'`
  - `is_active = TRUE`
- Se vuoi revocare accesso, imposta `is_active = FALSE`.

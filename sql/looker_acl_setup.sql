#standardSQL

-- ============================================================
-- VTRONIK - LOOKER STUDIO ROW-LEVEL SECURITY (ACL)
-- Mapping: user_email -> ov_codice_cliente
-- Dataset: sap_reporting
-- Project: vtronik-sap-reporting-cliente
-- ============================================================

-- 1) TABELLA ACL (many-to-many)
CREATE TABLE IF NOT EXISTS `vtronik-sap-reporting-cliente.sap_reporting.acl_utenti_clienti` (
  user_email STRING NOT NULL,
  ov_codice_cliente STRING NOT NULL,
  is_active BOOL NOT NULL,
  note STRING,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
);

-- 2) INSERIMENTO ESEMPI
-- Esegui solo come esempio iniziale e poi adatta ai tuoi utenti reali.
INSERT INTO `vtronik-sap-reporting-cliente.sap_reporting.acl_utenti_clienti`
  (user_email, ov_codice_cliente, is_active, note, created_at, updated_at)
VALUES
  ('cliente1@azienda.it', 'C0001', TRUE, 'accesso cliente 1', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP()),
  ('cliente1@azienda.it', 'C0002', TRUE, 'accesso cliente 1 su secondo codice', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP()),
  ('cliente2@azienda.it', 'C0100', TRUE, 'accesso cliente 2', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP());

-- 3) UPSERT DI MANUTENZIONE ACL (se devi aggiornare singole righe)
MERGE `vtronik-sap-reporting-cliente.sap_reporting.acl_utenti_clienti` AS t
USING (
  SELECT
    LOWER('cliente1@azienda.it') AS user_email,
    'C0001' AS ov_codice_cliente,
    TRUE AS is_active,
    'aggiornamento manuale' AS note
) AS s
ON LOWER(t.user_email) = s.user_email
   AND t.ov_codice_cliente = s.ov_codice_cliente
WHEN MATCHED THEN
  UPDATE SET
    is_active = s.is_active,
    note = s.note,
    updated_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN
  INSERT (user_email, ov_codice_cliente, is_active, note, created_at, updated_at)
  VALUES (s.user_email, s.ov_codice_cliente, s.is_active, s.note, CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP());

-- 3b) MASTER USER (vede tutto)
-- Convenzione: ov_codice_cliente = '__ALL__' => accesso globale
MERGE `vtronik-sap-reporting-cliente.sap_reporting.acl_utenti_clienti` AS t
USING (
  SELECT
    LOWER('master@azienda.it') AS user_email,
    '__ALL__' AS ov_codice_cliente,
    TRUE AS is_active,
    'master user con accesso completo' AS note
) AS s
ON LOWER(t.user_email) = s.user_email
   AND UPPER(TRIM(t.ov_codice_cliente)) = '__ALL__'
WHEN MATCHED THEN
  UPDATE SET
    is_active = s.is_active,
    note = s.note,
    updated_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN
  INSERT (user_email, ov_codice_cliente, is_active, note, created_at, updated_at)
  VALUES (s.user_email, s.ov_codice_cliente, s.is_active, s.note, CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP());

-- 4) QUERY LOOKER STUDIO (CUSTOM QUERY NEL DATA SOURCE)
-- Questa query NON va eseguita nella console BigQuery:
-- @DS_USER_EMAIL esiste solo nel data source di Looker Studio.
--
-- Copia/incolla questo blocco nel campo "Custom Query" della data source Looker:
/*
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
);
*/

-- 5) QUERY DI VALIDAZIONE (test accessi senza Looker)
-- Sostituisci l'email e verifica che i record siano quelli attesi.
SELECT
  d.ov_codice_cliente,
  COUNT(*) AS righe
FROM `vtronik-sap-reporting-cliente.sap_reporting.stato_ordini_cliente` AS d
WHERE EXISTS (
  SELECT 1
  FROM `vtronik-sap-reporting-cliente.sap_reporting.acl_utenti_clienti` AS a
  WHERE a.is_active = TRUE
    AND LOWER(a.user_email) = LOWER('cliente1@azienda.it')
    AND (
      UPPER(TRIM(a.ov_codice_cliente)) = '__ALL__'
      OR a.ov_codice_cliente = d.ov_codice_cliente
    )
)
GROUP BY d.ov_codice_cliente
ORDER BY d.ov_codice_cliente;

-- 6) QUERY AUDIT ACL (controllo mappings attivi)
SELECT
  LOWER(user_email) AS user_email_norm,
  ov_codice_cliente,
  is_active,
  note,
  created_at,
  updated_at
FROM `vtronik-sap-reporting-cliente.sap_reporting.acl_utenti_clienti`
ORDER BY user_email_norm, ov_codice_cliente;

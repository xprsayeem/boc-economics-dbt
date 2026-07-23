-- ============================================================================
-- [ACCOUNTADMIN] Register your RSA PUBLIC key for key-pair auth (Phase 1)
--
-- Setting RSA_PUBLIC_KEY on a user requires ACCOUNTADMIN (or SECURITYADMIN),
-- so switch roles first. Paste the value printed by generate_key.ps1 (the
-- public-key body with no header/footer and no line breaks).
-- Replace <YOUR_SNOWFLAKE_USER> with your login name.
-- ============================================================================
use role accountadmin;

alter user <YOUR_SNOWFLAKE_USER>
  set rsa_public_key = '<PASTE_PUBLIC_KEY_BODY_FROM_generate_key.ps1>';

-- Verify — RSA_PUBLIC_KEY_FP should now show a fingerprint (SHA256:...).
desc user <YOUR_SNOWFLAKE_USER>;

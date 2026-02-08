-- Expand billing_keys.enc_bill for app-layer encrypted payloads.
-- Required after introducing Fernet encryption-at-rest for billing keys.

ALTER TABLE billing_keys
    MODIFY COLUMN enc_bill VARCHAR(1024) NOT NULL;

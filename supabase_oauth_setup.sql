-- =============================================================================
-- INDISERV ANALYTICA — VERIFICACIÓN PRE-OAUTH DE DNI + SINCRONIZACIÓN OAUTH 2.0
-- Ejecutar en: Supabase Dashboard -> SQL Editor -> New Query -> Run
-- =============================================================================
-- Incluye:
--   1. public.verificar_dni_pre_oauth(p_dni): valida de forma segura (solo
--      booleanos, sin exponer nombres ni correos) que el DNI de 8 dígitos exista
--      en 'padron_oficial' / 'usuarios_app' ANTES de abrir Google o GitHub.
--   2. public.oauth_sync_operador(...): vincula/autentica la sesión OAuth
--      (JWT 'authenticated' de Google o GitHub) con el DNI verificado, registra
--      el equipo confiable y emite un 'session_token' de 15 minutos.
-- =============================================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- -----------------------------------------------------------------------------
-- 1. PRE-VALIDACIÓN DE DNI ANTES DE LANZAR OAUTH EN EL NAVEGADOR
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.verificar_dni_pre_oauth(
    p_dni text
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_dni text := btrim(COALESCE(p_dni, ''));
    v_en_padron boolean := false;
    v_ya_registrado boolean := false;
BEGIN
    IF v_dni !~ '^[0-9]{8}$' THEN
        RETURN jsonb_build_object(
            'ok', false,
            'existe', false,
            'en_padron', false,
            'ya_registrado', false,
            'error', 'El DNI debe contener exactamente 8 dígitos numéricos.'
        );
    END IF;

    SELECT EXISTS (
        SELECT 1 FROM public.padron_oficial WHERE btrim(dni) = v_dni
    ) INTO v_en_padron;

    SELECT EXISTS (
        SELECT 1 FROM public.usuarios_app WHERE btrim(dni) = v_dni
    ) INTO v_ya_registrado;

    RETURN jsonb_build_object(
        'ok', true,
        'existe', (v_en_padron OR v_ya_registrado),
        'en_padron', v_en_padron,
        'ya_registrado', v_ya_registrado
    );
END;
$$;

REVOKE ALL ON FUNCTION public.verificar_dni_pre_oauth(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.verificar_dni_pre_oauth(text) TO anon, authenticated, service_role;

-- -----------------------------------------------------------------------------
-- 2. SINCRONIZACIÓN POST-OAUTH (GOOGLE / GITHUB) VINCULADA AL DNI
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.oauth_sync_operador(
    p_dni text DEFAULT NULL,
    p_nickname text DEFAULT NULL,
    p_device_hash text DEFAULT NULL,
    p_device_label text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, extensions
AS $$
DECLARE
    v_uid uuid := auth.uid();
    v_email text := lower(btrim(COALESCE(auth.jwt() ->> 'email', '')));
    v_clean_dni text := btrim(COALESCE(p_dni, ''));
    v_clean_nick text := left(btrim(COALESCE(NULLIF(btrim(p_nickname), ''), split_part(v_email, '@', 1), 'Operador')), 40);
    v_dev_hash text := btrim(COALESCE(p_device_hash, ''));
    v_dev_label text := left(btrim(COALESCE(NULLIF(btrim(p_device_label), ''), 'Desktop OAuth')), 80);
    v_user RECORD;
    v_existing_dni RECORD;
    v_other_mail RECORD;
    v_raw_token text := NULL;
    v_token_hash text := NULL;
    v_expires_at timestamptz := NULL;
BEGIN
    IF v_uid IS NULL OR v_email = '' OR position('@' in v_email) = 0 THEN
        RETURN jsonb_build_object(
            'ok', false,
            'error', 'Sesión OAuth inválida o sin correo electrónico verificado.'
        );
    END IF;

    -- Caso A: El cliente envió el DNI pre-validado antes de iniciar OAuth
    IF v_clean_dni <> '' THEN
        IF v_clean_dni !~ '^[0-9]{8}$' THEN
            RETURN jsonb_build_object(
                'ok', false,
                'error', 'El DNI debe contener exactamente 8 dígitos numéricos.'
            );
        END IF;

        SELECT dni, correo, nickname
          INTO v_existing_dni
          FROM public.usuarios_app
         WHERE btrim(dni) = v_clean_dni
         LIMIT 1;

        IF FOUND THEN
            IF lower(btrim(COALESCE(v_existing_dni.correo, ''))) <> ''
               AND lower(btrim(v_existing_dni.correo)) <> v_email THEN
                RETURN jsonb_build_object(
                    'ok', false,
                    'error', 'El correo de Google/GitHub no coincide con el correo registrado para este DNI.'
                );
            END IF;
            UPDATE public.usuarios_app
               SET correo = v_email,
                   nickname = COALESCE(NULLIF(btrim(v_existing_dni.nickname), ''), v_clean_nick)
             WHERE btrim(dni) = v_clean_dni;
        ELSE
            IF NOT EXISTS (SELECT 1 FROM public.padron_oficial WHERE btrim(dni) = v_clean_dni) THEN
                RETURN jsonb_build_object(
                    'ok', false,
                    'error', 'El DNI ingresado no figura en el padrón oficial en Supabase.'
                );
            END IF;

            SELECT dni INTO v_other_mail
              FROM public.usuarios_app
             WHERE lower(btrim(COALESCE(correo, ''))) = v_email
             LIMIT 1;

            IF FOUND THEN
                RETURN jsonb_build_object(
                    'ok', false,
                    'error', 'Este correo social ya se encuentra vinculado a otro DNI en el sistema.'
                );
            END IF;

            INSERT INTO public.usuarios_app (dni, nickname, correo, password_hash)
            VALUES (
                v_clean_dni,
                v_clean_nick,
                v_email,
                'indiserv_v1$oauth$' || encode(gen_random_bytes(24), 'hex')
            );
        END IF;

        SELECT dni, correo, nickname
          INTO v_user
          FROM public.usuarios_app
         WHERE btrim(dni) = v_clean_dni
         LIMIT 1;
    ELSE
        -- Caso B: Respaldo sin DNI previo (búsqueda por correo)
        SELECT dni, correo, nickname
          INTO v_user
          FROM public.usuarios_app
         WHERE lower(btrim(COALESCE(correo, ''))) = v_email
         LIMIT 1;

        IF NOT FOUND THEN
            RETURN jsonb_build_object(
                'ok', true,
                'status', 'needs_dni',
                'correo', v_email
            );
        END IF;
    END IF;

    -- Registrar equipo confiable y emitir sesión de 15 min si existen las tablas
    IF v_dev_hash <> '' AND to_regclass('public.dispositivos_confiables') IS NOT NULL THEN
        INSERT INTO public.dispositivos_confiables (dni, device_hash, device_label, plataforma, ultimo_uso, revocado)
        VALUES (btrim(v_user.dni), v_dev_hash, v_dev_label, 'desktop', now(), false)
        ON CONFLICT (dni, device_hash)
        DO UPDATE SET
            device_label = EXCLUDED.device_label,
            ultimo_uso = now(),
            revocado = false;
    END IF;

    IF v_dev_hash <> '' AND to_regclass('public.sesiones_activas') IS NOT NULL THEN
        v_raw_token := encode(gen_random_bytes(32), 'hex');
        v_token_hash := encode(digest(v_raw_token, 'sha256'), 'hex');
        v_expires_at := now() + interval '15 minutes';

        INSERT INTO public.sesiones_activas (dni, device_hash, token_hash, expira_en, revocada)
        VALUES (btrim(v_user.dni), v_dev_hash, v_token_hash, v_expires_at, false);
    END IF;

    RETURN jsonb_build_object(
        'ok', true,
        'status', 'authenticated',
        'session_token', v_raw_token,
        'expires_at', v_expires_at,
        'user', jsonb_build_object(
            'dni', btrim(v_user.dni),
            'correo', btrim(v_user.correo),
            'nickname', COALESCE(NULLIF(btrim(v_user.nickname), ''), v_clean_nick),
            'rol', 'operator'
        )
    );
END;
$$;

REVOKE ALL ON FUNCTION public.oauth_sync_operador(text, text, text, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.oauth_sync_operador(text, text, text, text) TO authenticated, service_role;

COMMIT;

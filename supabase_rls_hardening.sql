-- =============================================================================
-- INDISERV ANALYTICA — BLINDAJE DE BASE DE DATOS (RLS + RPC SECURITY DEFINER)
-- Ejecutar en: Supabase Dashboard -> SQL Editor -> New Query -> Run
-- =============================================================================

BEGIN;

-- 1. HABILITAR ROW LEVEL SECURITY (RLS) EN LAS 4 TABLAS
ALTER TABLE public.usuarios_app ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.padron_oficial ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reportes_diagnostico ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sugerencias_locales ENABLE ROW LEVEL SECURITY;

-- 2. REVOCAR PRIVILEGIOS PELIGROSOS (DELETE / TRUNCATE / UPDATE DIRECTO) AL ROL ANON
REVOKE DELETE, UPDATE, TRUNCATE ON public.usuarios_app FROM anon;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.padron_oficial FROM anon;
REVOKE DELETE, TRUNCATE ON public.reportes_diagnostico FROM anon;
REVOKE DELETE, TRUNCATE ON public.sugerencias_locales FROM anon;

-- 3. ELIMINAR POLÍTICAS ABIERTAS PREVIAS (SI EXISTEN)
DO $$
DECLARE
    pol RECORD;
BEGIN
    FOR pol IN
        SELECT policyname, tablename
        FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename IN ('usuarios_app', 'padron_oficial', 'reportes_diagnostico', 'sugerencias_locales')
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', pol.policyname, pol.tablename);
    END LOOP;
END $$;

-- 4. FUNCIONES RPC (SECURITY DEFINER) PARA AUTENTICACIÓN Y REGISTRO SIN EXPONER TABLAS
--    Con estas funciones, el rol 'anon' JAMÁS necesita hacer SELECT sobre 'usuarios_app'
--    ni descargar 'padron_oficial'.

CREATE OR REPLACE FUNCTION public.autenticar_usuario(
    p_dni text,
    p_correo text,
    p_password_hash text
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_user RECORD;
BEGIN
    IF p_dni IS NULL OR p_correo IS NULL OR p_password_hash IS NULL THEN
        RETURN jsonb_build_object('ok', false);
    END IF;

    SELECT dni, correo, nickname, password_hash
      INTO v_user
      FROM public.usuarios_app
     WHERE dni = btrim(p_dni)
     LIMIT 1;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('ok', false);
    END IF;

    IF lower(btrim(v_user.correo)) = lower(btrim(p_correo))
       AND v_user.password_hash = btrim(p_password_hash) THEN
        RETURN jsonb_build_object(
            'ok', true,
            'dni', v_user.dni,
            'correo', v_user.correo,
            'nickname', COALESCE(v_user.nickname, 'Operador')
        );
    END IF;

    RETURN jsonb_build_object('ok', false);
END;
$$;

CREATE OR REPLACE FUNCTION public.verificar_padron_dni(
    p_dni text
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_padron RECORD;
BEGIN
    IF p_dni IS NULL OR length(btrim(p_dni)) < 8 THEN
        RETURN jsonb_build_object('existe', false);
    END IF;

    SELECT dni, nombres_completos, carrera
      INTO v_padron
      FROM public.padron_oficial
     WHERE dni = btrim(p_dni)
     LIMIT 1;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('existe', false);
    END IF;

    RETURN jsonb_build_object(
        'existe', true,
        'nombres', v_padron.nombres_completos,
        'carrera', v_padron.carrera,
        'ya_registrado', EXISTS (SELECT 1 FROM public.usuarios_app WHERE dni = btrim(p_dni))
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.registrar_usuario_seguro(
    p_dni text,
    p_nickname text,
    p_correo text,
    p_password_hash text
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_clean_dni text := btrim(COALESCE(p_dni, ''));
    v_clean_nick text := btrim(COALESCE(p_nickname, ''));
    v_clean_correo text := btrim(COALESCE(p_correo, ''));
    v_clean_hash text := btrim(COALESCE(p_password_hash, ''));
BEGIN
    IF length(v_clean_dni) < 8 OR v_clean_nick = '' OR v_clean_correo = '' OR v_clean_hash = '' THEN
        RETURN jsonb_build_object('ok', false, 'error', 'Datos de registro incompletos.');
    END IF;

    IF v_clean_hash NOT LIKE 'indiserv_v1$%' THEN
        RETURN jsonb_build_object('ok', false, 'error', 'Formato criptográfico de contraseña inválido.');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM public.padron_oficial WHERE dni = v_clean_dni) THEN
        RETURN jsonb_build_object('ok', false, 'error', 'El DNI no figura en el padrón oficial público UNMSM.');
    END IF;

    IF EXISTS (SELECT 1 FROM public.usuarios_app WHERE dni = v_clean_dni) THEN
        RETURN jsonb_build_object('ok', false, 'error', 'Este DNI ya tiene una cuenta registrada. Inicie sesión.');
    END IF;

    INSERT INTO public.usuarios_app (dni, nickname, correo, password_hash)
    VALUES (v_clean_dni, v_clean_nick, v_clean_correo, v_clean_hash);

    RETURN jsonb_build_object('ok', true);
END;
$$;

GRANT EXECUTE ON FUNCTION public.autenticar_usuario(text, text, text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.verificar_padron_dni(text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.registrar_usuario_seguro(text, text, text, text) TO anon, authenticated;

-- 5. POLÍTICAS RLS ESTRICTAS POR TABLA
--    a) usuarios_app y padron_oficial: CERO políticas SELECT/INSERT/UPDATE/DELETE para 'anon'.
--       Todo acceso pasa exclusivamente por las 3 funciones RPC SECURITY DEFINER de arriba.
--       Cualquier intento de 'GET /rest/v1/usuarios_app?select=*' o 'padron_oficial?select=*'
--       devuelve [] (0 filas expuestas).

--    b) reportes_diagnostico: lectura de tickets y escritura validada sin borrado
CREATE POLICY "reportes_select_valid_ticket"
    ON public.reportes_diagnostico
    FOR SELECT
    TO anon, authenticated
    USING (id_ticket IS NOT NULL AND length(btrim(id_ticket)) >= 4);

CREATE POLICY "reportes_insert_valid_ticket"
    ON public.reportes_diagnostico
    FOR INSERT
    TO anon, authenticated
    WITH CHECK (id_ticket IS NOT NULL AND length(btrim(id_ticket)) >= 6);

CREATE POLICY "reportes_update_valid_ticket"
    ON public.reportes_diagnostico
    FOR UPDATE
    TO anon, authenticated
    USING (id_ticket IS NOT NULL AND length(btrim(id_ticket)) >= 6)
    WITH CHECK (id_ticket IS NOT NULL AND length(btrim(id_ticket)) >= 6);

--    c) sugerencias_locales: inserción de sugerencias/honeytokens y lectura exclusiva de alertas HONEY-%
CREATE POLICY "sugerencias_insert_valid"
    ON public.sugerencias_locales
    FOR INSERT
    TO anon, authenticated
    WITH CHECK (id_ticket IS NOT NULL AND length(btrim(id_ticket)) >= 6);

CREATE POLICY "sugerencias_update_valid"
    ON public.sugerencias_locales
    FOR UPDATE
    TO anon, authenticated
    USING (id_ticket IS NOT NULL AND length(btrim(id_ticket)) >= 6)
    WITH CHECK (id_ticket IS NOT NULL AND length(btrim(id_ticket)) >= 6);

CREATE POLICY "sugerencias_select_only_honeytokens"
    ON public.sugerencias_locales
    FOR SELECT
    TO anon, authenticated
    USING (id_ticket LIKE 'HONEY-%');

COMMIT;

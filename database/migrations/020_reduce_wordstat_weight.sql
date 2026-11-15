-- Wordstat is a supporting signal, not a replacement for actual chart performance.
-- Games keep their separate 65% charts + 35% Whatstat audience formula.
DO $$
DECLARE
    definition TEXT;
    updated_definition TEXT;
BEGIN
    definition := pg_get_viewdef('v_category_weekly_score'::REGCLASS, true);
    updated_definition := replace(replace(definition, '0.85', '0.97'), '0.15', '0.03');

    IF updated_definition = definition THEN
        RAISE EXCEPTION 'v_category_weekly_score does not contain the expected 85/15 weights';
    END IF;

    EXECUTE 'CREATE OR REPLACE VIEW v_category_weekly_score AS ' || updated_definition;
END
$$;

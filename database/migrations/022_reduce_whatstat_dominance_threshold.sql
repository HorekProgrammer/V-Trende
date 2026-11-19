-- A Whatstat-only leader reaches the full 100% weight at a 50% lead over
-- second place. The rule remains limited to weeks from 2026-11-23 onward.
DO $$
DECLARE
    definition TEXT;
    updated_definition TEXT;
    old_expression CONSTANT TEXT :=
        'GREATEST(0.0, a.average_viewers::numeric / a.second_viewers::numeric - 1.0) * 0.20';
    new_expression CONSTANT TEXT :=
        'GREATEST(0.0, a.average_viewers::numeric / a.second_viewers::numeric - 1.0) * 0.40';
BEGIN
    definition := pg_get_viewdef('v_category_weekly_score'::REGCLASS, true);
    updated_definition := replace(definition, old_expression, new_expression);

    IF updated_definition = definition THEN
        RAISE EXCEPTION 'v_category_weekly_score does not contain the expected dominance expression';
    END IF;

    EXECUTE 'CREATE OR REPLACE VIEW v_category_weekly_score AS ' || updated_definition;
END
$$;

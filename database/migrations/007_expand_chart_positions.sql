ALTER TABLE trend_history
    DROP CONSTRAINT trend_history_position_check,
    ADD CONSTRAINT trend_history_position_check CHECK (position BETWEEN 1 AND 150);

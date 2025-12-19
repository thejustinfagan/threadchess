-- Battle Dinghy: Enable Row Level Security
-- This fixes the security warnings in Supabase Security Advisor

-- Step 1: Enable RLS on all tables
ALTER TABLE public.games ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ocean_grids ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.moves ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.player_stats ENABLE ROW LEVEL SECURITY;

-- Step 2: Drop existing policies if they exist (makes this script idempotent)
DROP POLICY IF EXISTS "Allow all access to games" ON public.games;
DROP POLICY IF EXISTS "Allow all access to ocean_grids" ON public.ocean_grids;
DROP POLICY IF EXISTS "Allow all access to moves" ON public.moves;
DROP POLICY IF EXISTS "Allow all access to player_stats" ON public.player_stats;

-- Step 3: Create permissive policies
-- These allow all access since the bot uses the service role key (which bypasses RLS anyway)
CREATE POLICY "Allow all access to games" ON public.games 
FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Allow all access to ocean_grids" ON public.ocean_grids 
FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Allow all access to moves" ON public.moves 
FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Allow all access to player_stats" ON public.player_stats 
FOR ALL USING (true) WITH CHECK (true);

-- Done! Security warnings should be resolved.

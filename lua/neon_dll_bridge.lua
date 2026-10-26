-------------------------------------------------------------------------------------------------
-- NEON DLL BRIDGE --
-- When SC4NEON.dll is installed, run_grid_balance_variables() is computed in C++ by the DLL.
-- Without the DLL, the original Lua version below (run_grid_balance_variables_lua) is used as before.
-- The DLL receives the same game values the Lua used (trend values, difficulty) and writes back every
-- grid_logic_var / power_company_buildings field, so reward conditions and LTEXT keep working unchanged.
-------------------------------------------------------------------------------------------------
if (neon == nil) then neon = {} end
-- Values shown by the power company office query that only the DLL computes (unsupported power plants).
-- They are 0 without the DLL instead of nil, so the query texts never fail.
for _, name in ipairs({"UNS_COAL_COUNT", "UNS_NAT_GAS_COUNT", "UNS_OIL_COUNT", "UNS_WIND_COUNT", "UNS_SOLAR_COUNT",
                "UNS_FISSION_COUNT", "UNS_WASTE_COUNT", "UNS_FUSION_COUNT", "UNS_OTHER_COUNT",
                "LARGE_OTHER_COUNT", "SMALL_OTHER_COUNT", "D_OTHER_POWER"}) do
    if (grid_logic_var[name] == nil) then grid_logic_var[name] = 0 end
end
-- Live output of waste-to-energy plants (same formula as the Lua version), used by the W2E query.
function neon_update_waste_to_energy_ratings()
    mwh_rating.ID_BB3500D0 = (math.floor((mwh_rating.ID_BB3500D0_A / math.max(grid_logic_var.L_WASTE_MAX_POWER + grid_logic_var.S_WASTE_MAX_POWER,1)*game.trend_value(game_trends.G_GARBAGE_TO_ENERGY,0)*0.1)+0.5))
    mwh_rating.ID_BB3500D1 = (math.floor((mwh_rating.ID_BB3500D1_A / math.max(grid_logic_var.L_WASTE_MAX_POWER + grid_logic_var.S_WASTE_MAX_POWER,1)*game.trend_value(game_trends.G_GARBAGE_TO_ENERGY,0)*0.1)+0.5))
    mwh_rating.ID_BB3500D2 = (math.floor((mwh_rating.ID_BB3500D2_A / math.max(grid_logic_var.L_WASTE_MAX_POWER + grid_logic_var.S_WASTE_MAX_POWER,1)*game.trend_value(game_trends.G_GARBAGE_TO_ENERGY,0)*0.1)+0.5))
    mwh_rating.ID_BB3500D3 = (math.floor((mwh_rating.ID_BB3500D3_A / math.max(grid_logic_var.L_WASTE_MAX_POWER + grid_logic_var.S_WASTE_MAX_POWER,1)*game.trend_value(game_trends.G_GARBAGE_TO_ENERGY,0)*0.1)+0.5))
    mwh_rating.ID_BB3500D4 = (math.floor((mwh_rating.ID_BB3500D4_A / math.max(grid_logic_var.L_WASTE_MAX_POWER + grid_logic_var.S_WASTE_MAX_POWER,1)*game.trend_value(game_trends.G_GARBAGE_TO_ENERGY,0)*0.1)+0.5))
    mwh_rating.ID_BB3500D5 = (math.floor((mwh_rating.ID_BB3500D5_A / math.max(grid_logic_var.L_WASTE_MAX_POWER + grid_logic_var.S_WASTE_MAX_POWER,1)*game.trend_value(game_trends.G_GARBAGE_TO_ENERGY,0)*0.1)+0.5))
    mwh_rating.ID_BB3500D6 = (math.floor((mwh_rating.ID_BB3500D6_A / math.max(grid_logic_var.L_WASTE_MAX_POWER + grid_logic_var.S_WASTE_MAX_POWER,1)*game.trend_value(game_trends.G_GARBAGE_TO_ENERGY,0)*0.1)+0.5))
    mwh_rating.ID_BB3500D7 = (math.floor((mwh_rating.ID_BB3500D7_A / math.max(grid_logic_var.L_WASTE_MAX_POWER + grid_logic_var.S_WASTE_MAX_POWER,1)*game.trend_value(game_trends.G_GARBAGE_TO_ENERGY,0)*0.1)+0.5))
    mwh_rating.ID_BB3500D8 = (math.floor((mwh_rating.ID_BB3500D8_A / math.max(grid_logic_var.L_WASTE_MAX_POWER + grid_logic_var.S_WASTE_MAX_POWER,1)*game.trend_value(game_trends.G_GARBAGE_TO_ENERGY,0)*0.1)+0.5))
    mwh_rating.ID_BB3500D9 = (math.floor((mwh_rating.ID_BB3500D9_A / math.max(grid_logic_var.L_WASTE_MAX_POWER + grid_logic_var.S_WASTE_MAX_POWER,1)*game.trend_value(game_trends.G_GARBAGE_TO_ENERGY,0)*0.1)+0.5))
    mwh_rating.ID_BB3500DA = (math.floor((mwh_rating.ID_BB3500DA_A / math.max(grid_logic_var.L_WASTE_MAX_POWER + grid_logic_var.S_WASTE_MAX_POWER,1)*game.trend_value(game_trends.G_GARBAGE_TO_ENERGY,0)*0.1)+0.5))
    mwh_rating.ID_BB3500DB = (math.floor((mwh_rating.ID_BB3500DB_A / math.max(grid_logic_var.L_WASTE_MAX_POWER + grid_logic_var.S_WASTE_MAX_POWER,1)*game.trend_value(game_trends.G_GARBAGE_TO_ENERGY,0)*0.1)+0.5))
    mwh_rating.ID_BB3500DC = (math.floor((mwh_rating.ID_BB3500DC_A / math.max(grid_logic_var.L_WASTE_MAX_POWER + grid_logic_var.S_WASTE_MAX_POWER,1)*game.trend_value(game_trends.G_GARBAGE_TO_ENERGY,0)*0.1)+0.5))
    mwh_rating.ID_BB3500DD = (math.floor((mwh_rating.ID_BB3500DD_A / math.max(grid_logic_var.L_WASTE_MAX_POWER + grid_logic_var.S_WASTE_MAX_POWER,1)*game.trend_value(game_trends.G_GARBAGE_TO_ENERGY,0)*0.1)+0.5))
    mwh_rating.ID_BB3500DE = (math.floor((mwh_rating.ID_BB3500DE_A / math.max(grid_logic_var.L_WASTE_MAX_POWER + grid_logic_var.S_WASTE_MAX_POWER,1)*game.trend_value(game_trends.G_GARBAGE_TO_ENERGY,0)*0.1)+0.5))
    mwh_rating.ID_BB3500DF = (math.floor((mwh_rating.ID_BB3500DF_A / math.max(grid_logic_var.L_WASTE_MAX_POWER + grid_logic_var.S_WASTE_MAX_POWER,1)*game.trend_value(game_trends.G_GARBAGE_TO_ENERGY,0)*0.1)+0.5))
    mwh_rating.ID_BB3501D0 = (math.floor((mwh_rating.ID_BB3501D0_A / math.max(grid_logic_var.L_WASTE_MAX_POWER + grid_logic_var.S_WASTE_MAX_POWER,1)*game.trend_value(game_trends.G_GARBAGE_TO_ENERGY,0)*0.1)+0.5))
    mwh_rating.ID_BB3501D1 = (math.floor((mwh_rating.ID_BB3501D1_A / math.max(grid_logic_var.L_WASTE_MAX_POWER + grid_logic_var.S_WASTE_MAX_POWER,1)*game.trend_value(game_trends.G_GARBAGE_TO_ENERGY,0)*0.1)+0.5))
    mwh_rating.ID_BB3501D2 = (math.floor((mwh_rating.ID_BB3501D2_A / math.max(grid_logic_var.L_WASTE_MAX_POWER + grid_logic_var.S_WASTE_MAX_POWER,1)*game.trend_value(game_trends.G_GARBAGE_TO_ENERGY,0)*0.1)+0.5))
    mwh_rating.ID_BB3501D3 = (math.floor((mwh_rating.ID_BB3501D3_A / math.max(grid_logic_var.L_WASTE_MAX_POWER + grid_logic_var.S_WASTE_MAX_POWER,1)*game.trend_value(game_trends.G_GARBAGE_TO_ENERGY,0)*0.1)+0.5))
    mwh_rating.ID_BB3501D4 = (math.floor((mwh_rating.ID_BB3501D4_A / math.max(grid_logic_var.L_WASTE_MAX_POWER + grid_logic_var.S_WASTE_MAX_POWER,1)*game.trend_value(game_trends.G_GARBAGE_TO_ENERGY,0)*0.1)+0.5))
    mwh_rating.ID_BB3501D5 = (math.floor((mwh_rating.ID_BB3501D5_A / math.max(grid_logic_var.L_WASTE_MAX_POWER + grid_logic_var.S_WASTE_MAX_POWER,1)*game.trend_value(game_trends.G_GARBAGE_TO_ENERGY,0)*0.1)+0.5))
    mwh_rating.ID_BB3501D6 = (math.floor((mwh_rating.ID_BB3501D6_A / math.max(grid_logic_var.L_WASTE_MAX_POWER + grid_logic_var.S_WASTE_MAX_POWER,1)*game.trend_value(game_trends.G_GARBAGE_TO_ENERGY,0)*0.1)+0.5))
    mwh_rating.ID_BB3501D7 = (math.floor((mwh_rating.ID_BB3501D7_A / math.max(grid_logic_var.L_WASTE_MAX_POWER + grid_logic_var.S_WASTE_MAX_POWER,1)*game.trend_value(game_trends.G_GARBAGE_TO_ENERGY,0)*0.1)+0.5))
    mwh_rating.ID_BB3501D8 = (math.floor((mwh_rating.ID_BB3501D8_A / math.max(grid_logic_var.L_WASTE_MAX_POWER + grid_logic_var.S_WASTE_MAX_POWER,1)*game.trend_value(game_trends.G_GARBAGE_TO_ENERGY,0)*0.1)+0.5))
    mwh_rating.ID_BB3501D9 = (math.floor((mwh_rating.ID_BB3501D9_A / math.max(grid_logic_var.L_WASTE_MAX_POWER + grid_logic_var.S_WASTE_MAX_POWER,1)*game.trend_value(game_trends.G_GARBAGE_TO_ENERGY,0)*0.1)+0.5))
    mwh_rating.ID_BB3501DA = (math.floor((mwh_rating.ID_BB3501DA_A / math.max(grid_logic_var.L_WASTE_MAX_POWER + grid_logic_var.S_WASTE_MAX_POWER,1)*game.trend_value(game_trends.G_GARBAGE_TO_ENERGY,0)*0.1)+0.5))
    mwh_rating.ID_BB3501DB = (math.floor((mwh_rating.ID_BB3501DB_A / math.max(grid_logic_var.L_WASTE_MAX_POWER + grid_logic_var.S_WASTE_MAX_POWER,1)*game.trend_value(game_trends.G_GARBAGE_TO_ENERGY,0)*0.1)+0.5))
    mwh_rating.ID_BB3501DC = (math.floor((mwh_rating.ID_BB3501DC_A / math.max(grid_logic_var.L_WASTE_MAX_POWER + grid_logic_var.S_WASTE_MAX_POWER,1)*game.trend_value(game_trends.G_GARBAGE_TO_ENERGY,0)*0.1)+0.5))
    mwh_rating.ID_BB3501DD = (math.floor((mwh_rating.ID_BB3501DD_A / math.max(grid_logic_var.L_WASTE_MAX_POWER + grid_logic_var.S_WASTE_MAX_POWER,1)*game.trend_value(game_trends.G_GARBAGE_TO_ENERGY,0)*0.1)+0.5))
    mwh_rating.ID_BB3501DE = (math.floor((mwh_rating.ID_BB3501DE_A / math.max(grid_logic_var.L_WASTE_MAX_POWER + grid_logic_var.S_WASTE_MAX_POWER,1)*game.trend_value(game_trends.G_GARBAGE_TO_ENERGY,0)*0.1)+0.5))
    mwh_rating.ID_BB3501DF = (math.floor((mwh_rating.ID_BB3501DF_A / math.max(grid_logic_var.L_WASTE_MAX_POWER + grid_logic_var.S_WASTE_MAX_POWER,1)*game.trend_value(game_trends.G_GARBAGE_TO_ENERGY,0)*0.1)+0.5))
end
run_grid_balance_variables_lua = run_grid_balance_variables
function run_grid_balance_variables(ret_type)
    if (neon.update == nil) then
        return run_grid_balance_variables_lua(ret_type)
    end
-- Determine if a bridge is present (unchanged from the Lua version)
    if (game.g_bridge_tile_count < unlock_variables.TRANS_SUBSTATION_60_MVA_S_BRIDGE_TILES) then
        unlock_variables.TRANS_SUBSTATION_60_MVA_S_BRIDGE = "No"
    else
        unlock_variables.TRANS_SUBSTATION_60_MVA_S_BRIDGE = "Yes"
    end
    local level = 2
    if (game.difficulty_level() == game_difficulty_level.EASY) then
        level = 0
    elseif (game.difficulty_level() == game_difficulty_level.MEDIUM) then
        level = 1
    end
    if (neon.update(game.trend_value(game_trends.G_POWER_DEMANDED,0),
                    game.trend_value(game_trends.G_POWER_EXPORTED,0),
                    game.trend_value(game_trends.G_POWER_IMPORTED,0),
                    game.trend_value(game_trends.G_POWER_PRODUCED,0),
                    game.trend_value(game_trends.G_GARBAGE_TO_ENERGY,0),
                    game.g_power_consumed,
                    game.g_power_production_capacity,
                    level)) then
        neon.export(grid_logic_var, power_company_buildings)
        neon_update_waste_to_energy_ratings()
    end
    if (ret_type ~= nil) then
        return neon.grid(ret_type)
    end
end

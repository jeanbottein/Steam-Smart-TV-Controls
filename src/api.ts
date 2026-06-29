import { callable } from "@decky/api";

export interface Brand {
  id: string;
  label: string;
}

export interface Tv {
  host: string;
  name: string;
  brand: string;
}

export interface Rule {
  display_id: string;
  host: string;
  input_id: string;
  enabled: boolean;
}

export interface Display {
  connector: string;
  id: string;
}

export interface Input {
  id: string;
  label: string;
}

export const listBrands = callable<[], Brand[]>("list_brands");
export const listTvs = callable<[], Tv[]>("list_tvs");
export const getSelectedTv = callable<[], string>("get_selected_tv");
export const setSelectedTv = callable<[host: string], void>("set_selected_tv");
export const listRules = callable<[], Rule[]>("list_rules");
export const listDisplays = callable<[], Display[]>("list_displays");
export const getInputs = callable<[host: string], Input[]>("get_inputs");
export const pairTv = callable<[host: string, name: string, brand: string], Tv>("pair_tv");
export const removeTv = callable<[host: string], void>("remove_tv");
export const switchInput = callable<[host: string, inputId: string], void>("switch_input");
export const setRule =
  callable<[displayId: string, host: string, inputId: string, enabled: boolean], void>("set_rule");
export const removeRule = callable<[displayId: string], void>("remove_rule");
export const isReachable = callable<[host: string], boolean>("is_reachable");
export const readLogs = callable<[], string>("read_logs");

export const tvLabel = (tv: Tv): string => tv.name || tv.host;

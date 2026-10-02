export interface RaceSummary {
	id: string;
	office: 'sen' | 'gov' | 'house';
	state: string;
	special: boolean;
	d: string;
	d_party: string;
	r: string;
	p: number;
	mu: number;
	q10: number;
	q90: number;
	poll_weight: number;
	n_polls: number;
	rule: string;
	p_runoff: number;
	incumbent_party: string;
}

export interface Chamber {
	holdover_dem: number;
	holdover_rep: number;
	seats_up: number;
	dem_seats_mean: number;
	rep_seats_mean: number;
	dem_seats_hist: Record<string, number>;
	rep_seats_hist: Record<string, number>;
	p_rep_control?: number;
	p_dem_control?: number;
	p_independents_decide?: number;
	p_any_independent_wins?: number;
	p_dem_majority?: number;
	p_rep_majority?: number;
	tipping_point?: Record<string, number>;
	by_scenario: Record<string, Partial<Chamber>>;
}

export interface Scenario {
	key: string;
	label: string;
	weight: number;
	shift: number;
}

export interface Summary {
	run_id: string;
	updated: string;
	as_of: string;
	days_to_election: number;
	election_date: string;
	n_sims: number;
	national: { sen: Chamber; gov: Chamber };
	generic_ballot: { margin: number; dem: number; rep: number; n_polls: number };
	scenarios: Scenario[];
	races: RaceSummary[];
	attribution: string[];
}

interface CitySelectorProps {
  cities: Array<{ city_id: string; label: string; simulation_ready: boolean }>;
  selectedCityId: string;
  onSelectCity: (cityId: string) => void;
}

export function CitySelector({ cities, selectedCityId, onSelectCity }: CitySelectorProps) {
  return (
    <nav className="city-selector-row">
      {cities.map((city) => (
        <button
          key={city.city_id}
          type="button"
          className={city.city_id === selectedCityId ? "city-card active" : "city-card"}
          onClick={() => onSelectCity(city.city_id)}
        >
          <strong>{city.label}</strong>
          <span>{city.simulation_ready ? "Live city pack" : "Schedule preview"}</span>
        </button>
      ))}
    </nav>
  );
}

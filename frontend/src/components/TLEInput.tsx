import React, { useState, useEffect } from "react";
import { Upload, Check, X, AlertCircle, Search, Satellite } from "lucide-react";
import { useMission } from "../context/MissionContext";
import { TLEData } from "../types";

interface TLEInputProps {
  tle: TLEData;
  onChange: (tle: TLEData) => void;
}

interface TLESource {
  id: string;
  name: string;
  url: string;
  description: string;
}

interface SatelliteData {
  name: string;
  line1: string;
  line2: string;
}

const TLEInput: React.FC<TLEInputProps> = ({ tle, onChange }) => {
  const { state, validateTLE } = useMission();
  const [isValidating, setIsValidating] = useState(false);
  const [showCelestrak, setShowCelestrak] = useState(false);
  const [tleSources, setTleSources] = useState<TLESource[]>([]);
  const [selectedSource, setSelectedSource] =
    useState<string>("celestrak_active");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SatelliteData[]>([]);
  const [isLoadingSources, setIsLoadingSources] = useState(false);
  const [isSearching, setIsSearching] = useState(false);

  // Load TLE sources on component mount
  useEffect(() => {
    loadTLESources();
  }, []);

  // Safety check for props - moved after hooks to comply with React rules
  if (!tle || !onChange) {
    return <div className="text-red-400">Error: Invalid TLE input props</div>;
  }

  const loadTLESources = async () => {
    setIsLoadingSources(true);
    try {
      const response = await fetch("/api/v1/tle/sources");
      const data = await response.json();
      setTleSources(data.sources);
    } catch (error) {
      console.error("Failed to load TLE sources:", error);
    } finally {
      setIsLoadingSources(false);
    }
  };

  const searchSatellites = async () => {
    if (!searchQuery.trim()) return;

    setIsSearching(true);
    try {
      const response = await fetch("/api/v1/tle/search", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: searchQuery,
          source: selectedSource,
        }),
      });
      const data = await response.json();
      setSearchResults(data.satellites || []);
    } catch (error) {
      console.error("Failed to search satellites:", error);
      setSearchResults([]);
    } finally {
      setIsSearching(false);
    }
  };

  const selectSatellite = (satellite: SatelliteData) => {
    onChange({
      name: satellite.name,
      line1: satellite.line1,
      line2: satellite.line2,
    });
    setShowCelestrak(false);
    setSearchResults([]);
    setSearchQuery("");
  };

  const handleTLEChange = (field: keyof TLEData, value: string) => {
    const newTLE = { ...tle, [field]: value };
    onChange(newTLE);
  };

  const handleValidate = async () => {
    if (!tle.name || !tle.line1 || !tle.line2) {
      return;
    }

    setIsValidating(true);
    try {
      await validateTLE(tle);
    } catch (error) {
      console.error("Validation error:", error);
    } finally {
      setIsValidating(false);
    }
  };

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      const content = e.target?.result as string;
      const lines = content.trim().split("\n");

      if (lines.length >= 3) {
        onChange({
          name: lines[0].trim(),
          line1: lines[1].trim(),
          line2: lines[2].trim(),
        });
      }
    };
    reader.readAsText(file);
  };

  const loadSampleTLE = () => {
    // ICEYE-X44 TLE (sample)
    onChange({
      name: "ICEYE-X44",
      line1:
        "1 99999U 24001A   25225.50000000  .00000000  00000-0  00000-0 0  9990",
      line2:
        "2 99999  97.4000 180.0000 0001000  90.0000 270.0000 15.20000000000000",
    });
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-white">TLE Data</h3>
        <div className="flex space-x-2">
          <button
            onClick={() => setShowCelestrak(!showCelestrak)}
            className="btn-secondary text-xs"
            disabled={isLoadingSources}
          >
            {isLoadingSources ? (
              <>
                <div className="loading-spinner w-3 h-3"></div>
                <span>Loading...</span>
              </>
            ) : (
              <>
                <Satellite className="w-3 h-3" />
                <span>Celestrak</span>
              </>
            )}
          </button>
          <label className="btn-secondary text-xs cursor-pointer">
            <Upload className="w-3 h-3" />
            <span>Upload</span>
            <input
              type="file"
              accept=".tle,.txt"
              onChange={handleFileUpload}
              className="hidden"
            />
          </label>
          <button
            onClick={loadSampleTLE}
            className="text-xs text-blue-400 hover:text-blue-300 underline"
          >
            Load Sample
          </button>
        </div>
      </div>

      {/* Celestrak Integration Panel */}
      {showCelestrak && (
        <div className="glass-panel rounded-lg p-4 mb-4">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-medium text-white flex items-center">
              <Satellite className="w-4 h-4 mr-2 text-blue-400" />
              Celestrak Satellite Catalog
            </h4>
            <button
              onClick={() => setShowCelestrak(false)}
              className="text-gray-400 hover:text-white"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Source Selection */}
          <div className="mb-3">
            <label className="block text-xs font-medium text-gray-400 mb-1">
              Satellite Catalog
            </label>
            <select
              value={selectedSource}
              onChange={(e) => setSelectedSource(e.target.value)}
              className="input-field w-full text-sm"
            >
              {tleSources.map((source) => (
                <option key={source.id} value={source.id}>
                  {source.name}
                </option>
              ))}
            </select>
          </div>

          {/* Search Interface */}
          <div className="mb-3">
            <label className="block text-xs font-medium text-gray-400 mb-1">
              Search Satellites
            </label>
            <div className="flex space-x-2">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="e.g., ICEYE, NOAA, ISS..."
                className="input-field flex-1 text-sm"
                onKeyPress={(e) => e.key === "Enter" && searchSatellites()}
              />
              <button
                onClick={searchSatellites}
                disabled={isSearching || !searchQuery.trim()}
                className="btn-primary text-xs"
              >
                {isSearching ? (
                  <div className="loading-spinner w-3 h-3"></div>
                ) : (
                  <Search className="w-3 h-3" />
                )}
              </button>
            </div>
          </div>

          {/* Search Results */}
          {searchResults.length > 0 && (
            <div className="max-h-48 overflow-y-auto custom-scrollbar">
              <div className="text-xs text-gray-400 mb-2">
                Found {searchResults.length} satellites
              </div>
              <div className="space-y-1">
                {searchResults.map((satellite, index) => (
                  <button
                    key={index}
                    onClick={() => selectSatellite(satellite)}
                    className="w-full text-left p-2 rounded bg-gray-800/50 hover:bg-gray-700/50 transition-colors"
                  >
                    <div className="text-sm text-white font-medium">
                      {satellite.name}
                    </div>
                    <div className="text-xs text-gray-400 truncate">
                      {satellite.line1.substring(0, 40)}...
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {searchQuery && searchResults.length === 0 && !isSearching && (
            <div className="text-center py-4 text-gray-500">
              <Search className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">No satellites found</p>
              <p className="text-xs">Try a different search term</p>
            </div>
          )}
        </div>
      )}

      <div className="space-y-3">
        <div>
          <label className="block text-xs font-medium text-gray-400 mb-1">
            Satellite Name
          </label>
          <input
            type="text"
            value={tle.name}
            onChange={(e) => handleTLEChange("name", e.target.value)}
            placeholder="e.g., ICEYE-X44"
            className="input-field w-full text-sm"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-400 mb-1">
            Line 1
          </label>
          <input
            type="text"
            value={tle.line1}
            onChange={(e) => handleTLEChange("line1", e.target.value)}
            placeholder="1 NNNNNC NNNNNAAA NNNNN.NNNNNNNN..."
            className="input-field w-full text-sm font-mono"
            maxLength={69}
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-400 mb-1">
            Line 2
          </label>
          <input
            type="text"
            value={tle.line2}
            onChange={(e) => handleTLEChange("line2", e.target.value)}
            placeholder="2 NNNNN NNN.NNNN NNNNNNNN..."
            className="input-field w-full text-sm font-mono"
            maxLength={69}
          />
        </div>
      </div>

      {/* Validation */}
      <div className="flex items-center space-x-2">
        <button
          onClick={handleValidate}
          disabled={isValidating || !tle.name || !tle.line1 || !tle.line2}
          className="btn-secondary text-xs flex-1"
        >
          {isValidating ? (
            <>
              <div className="loading-spinner w-3 h-3"></div>
              <span>Validating...</span>
            </>
          ) : (
            <>
              <Check className="w-3 h-3" />
              <span>Validate TLE</span>
            </>
          )}
        </button>
      </div>

      {/* Validation Result */}
      {state.validationResult && (
        <div
          className={`p-3 rounded-lg border ${
            state.validationResult.valid
              ? "bg-green-900/30 border-green-700 text-green-200"
              : "bg-red-900/30 border-red-700 text-red-200"
          }`}
        >
          <div className="flex items-center space-x-2">
            {state.validationResult?.valid ? (
              <Check className="w-4 h-4 text-green-400" />
            ) : (
              <X className="w-4 h-4 text-red-400" />
            )}
            <span
              className={`text-sm ${
                state.validationResult?.valid
                  ? "text-green-400"
                  : "text-red-400"
              }`}
            >
              {state.validationResult?.valid ? "TLE Valid" : "TLE Invalid"}
            </span>
          </div>

          {state.validationResult?.valid &&
            state.validationResult?.current_position && (
              <div className="text-xs space-y-1">
                <div>
                  <span className="text-gray-400">Current Position:</span>
                  <br />
                  <span>
                    {state.validationResult.current_position.latitude?.toFixed(
                      2,
                    )}
                    °,{" "}
                    {state.validationResult.current_position.longitude?.toFixed(
                      2,
                    )}
                    °,{" "}
                    {state.validationResult.current_position.altitude_km?.toFixed(
                      1,
                    )}
                    km
                  </span>
                </div>
                <div>
                  <span className="text-gray-400">Orbital Period:</span>{" "}
                  <span>
                    {state.validationResult.orbital_period_minutes?.toFixed(1)}
                    min
                  </span>
                </div>
              </div>
            )}

          {state.validationResult &&
            !state.validationResult.valid &&
            state.validationResult.error && (
              <div className="text-xs">
                <AlertCircle className="w-3 h-3 inline mr-1" />
                {state.validationResult.error}
              </div>
            )}
        </div>
      )}
    </div>
  );
};

export default TLEInput;

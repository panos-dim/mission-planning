import React from 'react';
import { Rocket, Code2 } from 'lucide-react';
import { useVisStore } from '../../store/visStore';

/**
 * UI Mode Toggle Switch
 * Allows switching between "Mission Planner" (simple) and "Developer" (all panels) modes
 * Located in header next to the 2D/3D view toggle
 */
const UIModeToggle: React.FC = () => {
  const { uiMode, toggleUIMode } = useVisStore();
  const isSimpleMode = uiMode === 'simple';

  return (
    <div className="flex items-center">
      {/* Toggle Switch */}
      <button
        onClick={toggleUIMode}
        className="relative flex items-center h-8 rounded-lg bg-gray-800 border border-gray-700 overflow-hidden"
        title={isSimpleMode ? 'Switch to Developer Mode' : 'Switch to Mission Planner Mode'}
      >
        {/* Mission Planner Option */}
        <div
          className={`
            flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium transition-all
            ${isSimpleMode 
              ? 'bg-blue-600 text-white' 
              : 'text-gray-400 hover:text-gray-200'
            }
          `}
        >
          <Rocket className="w-3.5 h-3.5" />
          <span>Planner</span>
        </div>

        {/* Developer Option */}
        <div
          className={`
            flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium transition-all
            ${!isSimpleMode 
              ? 'bg-purple-600 text-white' 
              : 'text-gray-400 hover:text-gray-200'
            }
          `}
        >
          <Code2 className="w-3.5 h-3.5" />
          <span>Dev</span>
        </div>
      </button>
    </div>
  );
};

export default UIModeToggle;

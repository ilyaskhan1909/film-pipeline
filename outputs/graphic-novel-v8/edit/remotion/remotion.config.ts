import {Config} from '@remotion/cli/config';

// Reuse the existing runtime without writing its shared dependency cache.
Config.setCachingEnabled(false);

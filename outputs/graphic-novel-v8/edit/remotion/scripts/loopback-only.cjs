const path = require('node:path');
// CLI 4.0.532 has no host flag. Restrict this process in memory, never patch dependencies on disk.
const config = require(path.join(path.dirname(require.resolve('@remotion/renderer')), 'port-config.js'));
if (typeof config.getHostToBind !== 'function' || typeof config.getHostsToTry !== 'function') {
  throw new Error('Loopback-only binding cannot be verified; refusing to start Studio.');
}
config.getHostToBind = () => '127.0.0.1';
config.getHostsToTry = () => ['127.0.0.1'];

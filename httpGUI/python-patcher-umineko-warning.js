'use strict';

let app = null;

// <python-pather-rest-lib.js should be included before this file>
// TODO: use proper javascript import
// When the main window is loaded
// - Vue components are defined
// - Main Vue instance, called 'app', is initialized
// - the subModHandles are retrieved from the python server to populate the app.subModList property
window.onload = function onWindowLoaded() {

  // Forces all links which have been sanitized to open in new window (in this case, markdown links)
  // See https://github.com/cure53/DOMPurify/issues/317#issuecomment-698800327
  DOMPurify.addHook('afterSanitizeAttributes', (node) => {
    if ('target' in node) {
      node.setAttribute('target', '_blank');
      node.setAttribute('rel', 'noopener');
    }
  });

  app = new Vue({
    el: '#app',
    data: {
      subModList: [],
      masonryInitialized: false,
      metaInfo: {
        buildInfo: '', // Installer Build Version and Date
        installerIsLatest: [null, ''], // 2- Tuple of whether installer is latest, and description of version information
        lockFileExists: false, // This indicates if a install is already running in a different instance, or a previous install was killed while running
        operatingSystem: '', // The operating system - either 'windows', 'linux', or 'mac'
        installAlreadyInProgress: false, // This is true if the install is currently running. Use to resume displaying an ongoing installation if the user accidentally closed the browser tab.
      },
      modalVisible: false,
    },
    methods: {
      nav(gameName) {
        setModNameAndNavigate(gameName);
      },
      clearModal() {
        doPost('clearLatestInstallerWarning', [], () => {});
        this.modalVisible = false;
      },
    },
    computed: {
      versionInfoAvailable() {
        return this.metaInfo.installerIsLatest[0] !== null;
      },
    },
    watch: {

    },
    updated() {
      // call initializeMasonry() from the theme's javascript js/script.js, on the first update call
      if (!this.masonryInitialized) {
        this.masonryInitialized = true;
        initializeMasonry();
      }
    },
    created() {
      // populate the app.subModList with subMods from the python server
      doPost('subModHandles', [], (responseData) => {
        app.subModList = responseData.subModHandles;
        const modNameToSubModHandleMap = {};
        console.log(responseData);
        responseData.subModHandles.forEach((subModHandle) => {
          modNameToSubModHandleMap[subModHandle.modName] = subModHandle;
        });

        app.metaInfo = responseData.metaInfo;
        if (app.metaInfo.installerIsLatest[0] !== true) {
          app.modalVisible = true;
        }

        // Force user back to the install page if the tried to leave
        if (app.metaInfo.installAlreadyInProgress) {
          window.location = 'installer.html';
        }
      });
    },
  });
};

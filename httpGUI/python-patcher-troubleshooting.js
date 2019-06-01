'use strict';

let app = null;

// <python-pather-rest-lib.js should be included before this file>
// TODO: use proper javascript import
// When the main window is loaded
// - Vue components are defined
// - Main Vue instance, called 'app', is initialized
// - the subModHandles are retrieved from the python server to populate the app.subModList property
window.onload = function onWindowLoaded() {
  app = new Vue({
    el: '#app',
    data: {
      uniqueSubMods: [],
    },
    methods: {
      troubleshoot(action, subModToInstall, installPath) {
        doPost('troubleshoot', { action: action, subMod: subModToInstall, installPath }, (responseData) => {
          if (responseData.error !== undefined) {
            alert(responseData.error);
          }
        });
      },
    },
    computed: {

    },
    watch: {

    },
    created() {
    },
  });

  // populate the app.subModList with subMods from the python server
  doPost('subModHandles', [], (responseData) => {
    console.log(responseData);
  });

  doPost('gamePaths', { id: null }, (allDetectedSubMods) => {
    const pathToSubModMap = {};
    allDetectedSubMods.forEach((element) => {
      pathToSubModMap[element.path] = element;
    });
    // filter down such that there is only one submod per path
    app.uniqueSubMods = Object.values(pathToSubModMap);
    console.log(app.uniqueSubMods);
  });
};

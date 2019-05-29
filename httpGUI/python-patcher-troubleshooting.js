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
    },
    methods: {
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
};

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
      uniqueSubMods: [],
      subModExtraProperties: {
        'Umineko Question (Ch. 1-4)': {
          img: 'img/games/header_umineko_question.png',
          dataFilter: 'Question Arcs',
        },
        'Umineko Answer (Ch. 5-8)': {
          img: 'img/games/header_umineko_answer.png',
          dataFilter: 'Answer Arcs',
        },
        'Umineko Tsubasa': {
          img: 'img/games/header_umineko_tsubasa.png',
          dataFilter: 'Bonus Content',
        },
        'Umineko Hane': {
          img: 'img/games/header_umineko_hane.png',
          dataFilter: 'Bonus Content',
        },
        'Umineko Saku': {
          img: 'img/games/header_umineko_saku.png',
          dataFilter: 'Bonus Content'
        },
        'Console Arcs': {
          img: 'img/games/console.png',
          dataFilter: 'Console Arcs',
        },
        'Onikakushi Ch.1': {
          img: 'img/games/header1.png',
          dataFilter: 'Question Arcs',
        },
        'Watanagashi Ch.2': {
          img: 'img/games/header2.png',
          dataFilter: 'Question Arcs',
        },
        'Tatarigoroshi Ch.3': {
          img: 'img/games/header3.png',
          dataFilter: 'Question Arcs',
        },
        'Himatsubushi Ch.4': {
          img: 'img/games/header4.png',
          dataFilter: 'Question Arcs',
        },
        'Meakashi Ch.5': {
          img: 'img/games/header5.png',
          dataFilter: 'Answer Arcs',
        },
        'Tsumihoroboshi Ch.6': {
          img: 'img/games/header6.png',
          dataFilter: 'Answer Arcs',
        },
        'Minagoroshi Ch.7': {
          img: 'img/games/header7.png',
          dataFilter: 'Answer Arcs',
        },
        'Matsuribayashi Ch.8': {
          img: 'img/games/header8.png',
          dataFilter: 'Answer Arcs',
        },
        'Rei': {
          img: 'img/games/header9.png',
          dataFilter: 'Bonus Content',
        },
      },
      // Data filters are defined manually so you can set the order
      dataFilters: ['Question Arcs', 'Answer Arcs', 'Console Arcs', 'Bonus Content'],
      currentDataFilter: null,
      masonryInitialized: false,
      donationProgress: 'N months',
      donationMonthsRemaining: 'XXX%',
      metaInfo: {
        buildInfo: '', // Installer Build Version and Date
        installerIsLatest: [null, ''], // 2- Tuple of whether installer is latest, and description of version information
        lockFileExists: false, // This indicates if a install is already running in a different instance, or a previous install was killed while running
        operatingSystem: '', // The operating system - either 'windows', 'linux', or 'mac'
        installAlreadyInProgress: false, // This is true if the install is currently running. Use to resume displaying an ongoing installation if the user accidentally closed the browser tab.
        donationMonthsRemaining: '', // How many months the server can be paid for with current funding
        donationProgressPercent: '', // How close funding is to the 12 month donation goal, in percent
      },
      modalVisible: false,
    },
    methods: {
      nav(gameName) {
        setModNameAndNavigate(gameName, gameName.toLowerCase().includes('umineko') ? 'umineko-warning.html' : 'installer.html');
      },
      // if subModExtraProperties missing a game, use wrong image
      // to make it obvious that the table needs to be updated
      getSubModExtraProperties(name) {
        return _.get(this.subModExtraProperties, name, {
          img: 'img/umineko/sprite_potato.png',
          dataFilter: 'Question Arcs',
        });
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
      uminekoSubMods() {
        return this.uniqueSubMods.filter((s) => s.family.toLowerCase().includes('umineko'));
      },
      higurashiSubMods() {
        return this.uniqueSubMods.filter((s) => s.family.toLowerCase().includes('higurashi'));
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

        app.uniqueSubMods = Object.values(modNameToSubModHandleMap);
        app.uniqueSubMods.sort((a, b) => a.id - b.id);
        console.log(app.uniqueSubMods);

        // Force user back to the install page if the tried to leave
        if (app.metaInfo.installAlreadyInProgress) {
          window.location = 'installer.html';
        }
      });
    },
  });
};

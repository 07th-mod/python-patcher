'use strict';

// DEPENDENCIES: This file depends on `python-patcher-rest-lib.js`. Make sure that file is loaded first.

Vue.component('dropdown-game-menu', {
  props: ['handles'],
  data() {
    return {};
  },
  computed: {
    families() {
      const modNameToSubModHandleMap = {};
      this.handles.forEach((subModHandle) => {
        modNameToSubModHandleMap[subModHandle.modName] = subModHandle;
      });

      // Sort by id
      const uniqueSubMods = Object.values(modNameToSubModHandleMap);
      uniqueSubMods.sort((a, b) => a.id - b.id);

      // group by family
      const families = _.groupBy(uniqueSubMods, subMod => subMod.family);

      // for purposes of display, umineko and umineko_nscripter are the same group.
      if (families.umineko !== undefined && families.umineko_nscripter !== undefined) {
        families.umineko = families.umineko.concat(families.umineko_nscripter);
        delete families.umineko_nscripter;
      }

      return families;
    },
  },
  methods: {
    remapFamily(familyName) {
      // For now just append "When They Cry" - if other games added, use a dictionary
      return `${familyName} When They Cry`;
    },
    setModNameAndNavigate(modName) {
      setModNameAndNavigate(modName);
    },
  },
  template: `
  <ul class="menu">
  <li class="has-dropdown" v-for='(modsInFamily, family, index) in families'>
      <a target="_self">{{ remapFamily(family) }}</a>
      <ul>
          <li v-for='num in modsInFamily'><a v-on:click="setModNameAndNavigate(num.modName)">{{ num.modName }}</a></li>
      </ul>
  </li>
  </ul>
  `,
});

// This component creates a snackbar (temporary popup at bottom of the screen)
// when a POST error occurs. You are currently only allowed one snack bar per page.
// To use, add a <snack-bar></snack-bar> element inside your main vue #app section
Vue.component('snack-bar', {
  data() {
    return {
      toastMessage: null,
      toastVisible: false,
      toastDismissalID: null,
      toastCount: 0,
    };
  },
  mounted() {
    // This is a global function defined in this file. It registers
    // which function should be called on a POST error
    setPOSTNotificationErrorCallback(this.showToast);
  },
  methods: {
    showToast(toastMessage) {
      this.toastCount += 1;
      this.toastMessage = toastMessage;
      this.toastVisible = true;

      // To prevent repeated fade in/out, cancel dismissal when a new toast received
      if (this.toastDismissalID !== null) {
        clearTimeout(this.toastDismissalID);
      }
      this.toastDismissalID = setTimeout(() => { this.toastVisible = false; }, 8000);
    },
  },
  template: `<transition name="fade">
  <div id="snackbar" v-show="toastVisible">{{ toastCount }}x {{ toastMessage }}</div>
  </transition>`,
});

/*:
 * @plugindesc Custom Menu Call
 * @author Markus Schatten & ChatGPT
 *
 * @param Menu Map ID
 * @desc The ID of the map that should be displayed when the menu is called.
 * @default 6
 *
 * @param Original Map ID Variable
 * @desc The ID of the variable that stores the original map ID.
 * @default 98
 *
 * @param Original X Coordinate Variable
 * @desc The ID of the variable that stores the original X coordinate.
 * @default 99
 *
 * @param Original Y Coordinate Variable
 * @desc The ID of the variable that stores the original Y coordinate.
 * @default 100
 *
 * @param Exit Common Event ID
 * @desc The ID of the common event that is run when the player exits the menu map.
 * @default 7
 *
 * @param Disabled Menu Maps
 * @desc A comma-separated list of map IDs on which the menu is disabled.
 * @default 
 *
 * @help This plugin replaces the default menu call with a custom function.
 * When the player presses the menu button, they will be transferred to the map
 * specified by the Menu Map ID parameter. If the player is already on this map
 * and they press the menu button, they will be transferred back to their original location.
 */

(function() {
    var parameters = PluginManager.parameters('MStablemenu');
    var menuMapId = Number(parameters['Menu Map ID'] || 6);
    var originalMapIdVariable = Number(parameters['Original Map ID Variable'] || 98);
    var originalXVariable = Number(parameters['Original X Coordinate Variable'] || 99);
    var originalYVariable = Number(parameters['Original Y Coordinate Variable'] || 100);
    var exitEventID = Number(parameters['Exit Common Event ID'] || 7);
    var disabledMenuMaps = String(parameters['Disabled Menu Maps'] || "").split(',').map(Number);

    var _Scene_Map_updateScene = Scene_Map.prototype.updateScene;
    Scene_Map.prototype.updateScene = function() {
        _Scene_Map_updateScene.call(this);
        if (this.isMenuCalled()) {
            this.callMenu();
        }
    };

    Scene_Map.prototype.isMenuCalled = function() {
        return Input.isTriggered('menu') && !disabledMenuMaps.includes($gameMap.mapId());
    };

    Scene_Map.prototype.callMenu = function() {
        SoundManager.playOk();
        if ($gameMap.mapId() !== menuMapId) {
            $gameVariables.setValue(originalMapIdVariable, $gameMap.mapId());
            $gameVariables.setValue(originalXVariable, $gamePlayer.x);
            $gameVariables.setValue(originalYVariable, $gamePlayer.y);
            $gamePlayer.reserveTransfer(menuMapId, $gamePlayer.x, $gamePlayer.y);
        } else {
            var originalMapId = $gameVariables.value(originalMapIdVariable);
            var originalX = $gameVariables.value(originalXVariable);
            var originalY = $gameVariables.value(originalYVariable);
            $gameTemp.reserveCommonEvent(exitEventID);
            $gamePlayer.reserveTransfer(originalMapId, originalX, originalY);
        }
        this._waitCount = 2;
    };
})();


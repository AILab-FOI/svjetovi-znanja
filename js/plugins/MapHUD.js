//=============================================================================
// MapHUD.js
//=============================================================================

/*:
 * @plugindesc Simple HUD plugin for thalesgal.
 * @author John Clifford (Trihan)
 *
 * @param X
 * @desc The x coordinate of the window
 * @default 0
 *
 *
 * @param Y
 * @desc The y coordinate of the window
 * @default 0
 *
 *
 * @param Maps
 * @desc List of maps to include (comma , separated)
 * @default ''
 *
 * @help
 *
 * Just puts a HUD on the screen that shows the level/HP/MP of the party leader.
 *
 */

(function() {
    var parameters = PluginManager.parameters('MapHUD');
    
    function Window_HUD() {
        this.initialize.apply(this, arguments);
    }
    
    Window_HUD.prototype = Object.create(Window_Base.prototype);
    Window_HUD.prototype.constructor = Window_HUD;
    
    Window_HUD.prototype.initialize = function() {
        Window_Base.prototype.initialize.call(this, parameters['X'], parameters['Y'], 200, 150);
        this.opacity = 100;
    };
    
    Window_HUD.prototype.update = function() {
        this.contents.clear();
        this.drawLeaderHUD();
    };

    function checkMap() {
	var mapname = $dataMapInfos[$gameMap.mapId()].name;
	var maps = parameters[ "Maps" ].split(",");
	for( var i in maps )
	{
	    if( maps[ i ] == mapname )
	    {
		return true;
	    }
	}
	return false;
    }
    
    Window_HUD.prototype.drawLeaderLevel = function(leader, x, y) {
        this.changeTextColor(this.systemColor());
        this.drawText("Rz", 10, 0, 30);
        this.resetTextColor();
        this.drawText(leader.level, 30, 0, 30, 'right');
    };
    
    Window_HUD.prototype.drawLeaderHUD = function() {
        var leader = $gameParty.members()[0];
        this.drawLeaderLevel(leader, 10, 0);
        this.drawActorHp(leader, 10, this.lineHeight(), 100);
        this.drawActorMp(leader, 10, this.lineHeight() * 2, 100);       
    };
    
    _Scene_Map_createAllWindows = Scene_Map.prototype.createAllWindows;
    Scene_Map.prototype.createAllWindows = function() {
        _Scene_Map_createAllWindows.call(this);
	if( checkMap() )
	{
            this._hudWindow = new Window_HUD();
            this.addChild(this._hudWindow);
	}
    };
        
})();

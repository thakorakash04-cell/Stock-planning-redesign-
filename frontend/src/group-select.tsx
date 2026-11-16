import GroupSelector from './grouping-selector';
import TableViewSwitch from './table-view';
import {groupColumns} from './grouping';
export default function GroupSelect(props:Parameters<typeof GroupSelector>[0]){return <GroupSelector {...props} viewSwitch={props.scope?<TableViewSwitch scope={props.scope} grouped={groupColumns(props.value).length>0}/>:undefined}/>}

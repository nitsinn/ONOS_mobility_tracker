package org.student.idlocatortracker;

import org.onosproject.core.ApplicationId;
import org.onosproject.core.CoreService;
import org.osgi.service.component.annotations.Component;
import org.osgi.service.component.annotations.Reference;
import org.osgi.service.component.annotations.ReferenceCardinality;
import org.osgi.service.component.annotations.Activate;
import org.osgi.service.component.annotations.Deactivate;

@Component(immediate = true)
public class AppComponent {

    @Reference(cardinality = ReferenceCardinality.MANDATORY)
    protected CoreService coreService;

    @Activate
    protected void activate() {
        ApplicationId appId = coreService.registerApplication("org.student.idlocatortracker.app");
        System.out.println("AppComponent started with App ID: " + appId);
    }

    @Deactivate
    protected void deactivate() {
        System.out.println("AppComponent stopped");
    }
}
